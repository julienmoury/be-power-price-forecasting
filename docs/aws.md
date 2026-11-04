# Running on AWS

The live forecast runs on AWS: the computation every evening, the data, the API (online
all the time) and a public page. GitHub Actions only tests and deploys. The code of the
forecast is unchanged: AWS runs `scripts/live_forecast.py` on a working directory filled
from S3, and serves `src/be_power_forecast/api/app.py` as it is.

Region: `eu-west-1` (Ireland). Infrastructure: Terraform in [`infra/`](../infra), plus a
CloudFormation stack deployed once by hand ([`infra/bootstrap/bootstrap.yaml`](../infra/bootstrap/bootstrap.yaml)).
Expected cost: about 1.5 $ a month (see [Costs](#9-costs)).

## Architecture

```
EventBridge Scheduler ──17:30 / 20:30 UTC──▶ ECS Fargate task (2 vCPU, 8 GB)
                                             python scripts/aws_run.py
                                               │  1. download cache/ and state/
                                               │  2. scripts/live_forecast.py, unchanged
                                               │  3. upload what changed
          ┌────────────────────────────────────┼─────────────────────┐
          ▼                                    ▼                     ▼
  S3 data bucket (private)            S3 site bucket (private)   Lambda configuration
  cache/  ENTSO-E, SMARD downloads    index.html, compare.png    (new execution
  state/  results/forecasts/live/             │                   environments)
          results/dnn/live/                   ▼                     │
          results/live/                  CloudFront (OAC) ──▶ public page
          live/                                                     │
          │                                                         ▼
          └──── state/results/forecasts/live/*.csv ──▶ Lambda (same image, Web Adapter)
                                                       public function URL: the API
GitHub Actions: ci.yml (tests, Terraform checks, image), deploy.yml (plan / apply, image
to ECR), sync-secrets.yml (ENTSO-E key to SSM), sync-databricks.yml (3 CSV to Databricks),
seed-state.yml (one-off), live.yml (fallback, by hand).
```

| Piece | What it is |
|---|---|
| ECR `be-power-forecast` | One image for the task and the API, tagged with the commit SHA; the last 5 are kept. |
| S3 `be-power-forecast-data-<account>` | Private, versioned (old versions expire after 30 days), encrypted, public access blocked, HTTPS only. `cache/`: the former Actions cache. `state/`: the live files, under their repository paths. |
| ECS Fargate `be-power-forecast-live` | 2 vCPU, 8 GB, default VPC, public subnet, public IP (no NAT gateway). Logs: `/ecs/be-power-forecast-live`, 14 days. |
| EventBridge Scheduler | `cron(30 17 * * ? *)` and `cron(30 20 * * ? *)` UTC, as the former crons; the second run skips a day already forecast. |
| SSM `/be-power-forecast/entsoe-api-key` | `SecureString`, standard tier; injected into the task as `ENTSOE_API_KEY`. |
| Lambda `be-power-forecast-api` | Same image, AWS Lambda Web Adapter 1.1.0, 2048 MB, 30 s, public function URL (no authentication, CORS for any origin, `GET` and `POST`, no credentials). Reserved concurrency left unset. Logs: 14 days. |
| S3 `be-power-forecast-site-<account>` + CloudFront | Private bucket read by CloudFront through Origin Access Control: `index.html` and `compare.png`. |
| Budget `be-power-forecast-monthly` | 5 $ a month, e-mail at 80 % and 100 % of actual costs. |

### What the evening run reads and writes

`scripts/aws_run.py` builds the same tree as a checkout of the repository, so that
`live_forecast.py` (`BE_REPO_ROOT` set to it) reads and writes the same files:

| Path | Read | Written | Where it lives |
|---|---|---|---|
| `data/raw/BE.csv` (Lago et al. data, joined before 2015-01-05) | yes | | image |
| `data/raw/dnn_hyperparameters_BE.json` | yes | | image |
| `data/cache/{prices_BE,generation_FR,load_FR}_2015-01-01_2026-09-30.parquet` (ENTSO-E download of phase B, read the first time only) | yes | if missing | `cache/` |
| `data/cache/{prices_BE,generation_FR,load_FR}_live.parquet` (ENTSO-E series, extended every day) | yes | yes | `cache/` |
| `results/forecasts/live/forecasts.csv`, `dnn_forecasts.csv` | yes | yes | `state/` |
| `results/dnn/live/summary.csv` (DNN training records) | yes | yes | `state/` |
| `results/live/realised.csv` (SMARD, CC BY 4.0) | yes | yes | `state/` |
| `live/README.md`, `live/compare.png` (page; the chart is removed on days without one) | | yes | `state/`, and the site bucket as HTML |

`results/forecasts/phase_b/` (backtests) is not read by the evening run; the API reads it
from the image. Only changed files are uploaded; files the run removed (the chart) are
removed from `state/`. When the computation fails, nothing is uploaded. When `state/` is
empty, the run stops (exit code 2) instead of starting a new live history: seed it first
(step 6).

The ENTSO-E data only ever go to the private data bucket. The site bucket only receives the
page: our forecasts and the SMARD prices, with their source, as on the repository page.

### Memory of the task: 8 GB

The brief asked for 4 GB, raised to 8 GB if needed. It is needed: the four DNNs train in
parallel in four processes, each with its own TensorFlow and its own copy of the 4-year
input window. Measured locally on one delivery day (`scripts/run_dnn.py --days 1 --jobs 4`,
the same training as the live run), the four workers and their parent used about 2.5 GB
(proportional set size, shared libraries counted once) during training, and up to 5.3 GB
summed resident memory, before the live run's own frame and LEAR ensemble. That leaves too little room under 4 GB, and an
out-of-memory kill would lose the day's forecast. 8 GB adds about 0.2 $ a month. Change it
with the Terraform variable `task_memory` (2 vCPU allows 4 to 16 GB).

### The API on Lambda

At a cold start, `python -m be_power_forecast.cloud` copies
`state/results/forecasts/live/forecasts.csv` and `dnn_forecasts.csv` to `/tmp/api`, points
`BE_LIVE_PATH` and `BE_DNN_LIVE_PATH` at them, and starts uvicorn on port 8080 behind the
Web Adapter (readiness check: `/health`). A file it cannot fetch keeps the copy of the
image (the live forecasts as of the build), so the service always starts. The phase B
backtests come from the image.

The ENTSO-E prices are not given to Lambda: `BE_PRICE_PATH` points to a file that does not
exist. `app.py` then behaves exactly as it does locally without `prices_BE.parquet`: the
price loader fails once at start (logged as `could not load prices`), `/health` answers
`"status": "ok"` with `"prices": false`, there is no naive fallback, and the last servable
day is the last LEAR forecast. A day inside the served range without a LEAR forecast
answers `503 no LEAR forecast and no price for <day>`; a day outside it `404`.

The service reads its files once per execution environment. After a run that changed the
forecasts, `aws_run.py` changes the `BE_STATE_VERSION` environment variable of the
function (Terraform ignores it), so Lambda starts new environments, which read the new
files.

## Deployment

The commands below are run once, in order, from a checkout of the repository on a machine
where the AWS CLI is signed in to the account (`aws sts get-caller-identity` works) and the
GitHub CLI to the repository (`gh auth status`). After step 4, every push to `main`
deploys through `.github/workflows/deploy.yml` with OIDC: no AWS key is stored anywhere.

```bash
export AWS_REGION=eu-west-1
```

```bash
export REPO=julienmoury/be-power-price-forecasting
```

### 1. Check the account

```bash
aws sts get-caller-identity
```

Check: the account ID is the right one, and the ARN is your own user or SSO role.

```bash
aws freetier get-account-plan-state --region us-east-1
```

Check: the plan (`FREE` or `PAID`) and its state. On the free plan, the costs below are
taken from the credits.

```bash
aws ecs list-clusters --region "$AWS_REGION"
```

```bash
aws lambda get-account-settings --region "$AWS_REGION" --query 'AccountLimit.{concurrency: ConcurrentExecutions, unreserved: UnreservedConcurrentExecutions}'
```

```bash
aws service-quotas get-service-quota --region "$AWS_REGION" --service-code fargate --quota-code L-3032A538 --query 'Quota.{name: QuotaName, value: Value}'
```

Check: the three commands answer without `AccessDenied` or `SubscriptionRequiredException`
(ECS, Lambda and Fargate are open); the Fargate On-Demand vCPU quota is at least 2; the
Lambda concurrency is at least 10. Nothing is reserved, so 10 is enough.

```bash
aws ec2 describe-vpcs --region "$AWS_REGION" --filters Name=is-default,Values=true --query 'Vpcs[].VpcId' --output text
```

Check: a VPC ID is printed (the default VPC, which the task uses). A new account has one in
every region.

### 2. Deploy the bootstrap stack

The stack creates the GitHub OIDC provider, the deploy role (only workflows of
`julienmoury/be-power-price-forecasting` can assume it), the read-only role of
`sync-databricks.yml`, the permissions boundary of the roles Terraform creates, and the
Terraform state bucket and lock table (DynamoDB, on demand).

```bash
aws iam list-open-id-connect-providers --query 'OpenIDConnectProviderList[].Arn' --output text
```

If an ARN ending in `token.actions.githubusercontent.com` is printed, the account already
has the provider: add `--parameter-overrides ExistingOidcProviderArn=<that ARN>` to the
next command.

```bash
aws cloudformation deploy --region "$AWS_REGION" --stack-name be-power-forecast-bootstrap --template-file infra/bootstrap/bootstrap.yaml --capabilities CAPABILITY_NAMED_IAM
```

```bash
aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name be-power-forecast-bootstrap --query 'Stacks[0].{status: StackStatus, outputs: Outputs[].[OutputKey, OutputValue]}' --output table
```

Check: `CREATE_COMPLETE`, and seven outputs (`DeployRoleArn`, `ReadOnlyRoleArn`,
`StateBucket`, `LockTable`, `DataBucket`, `SiteBucket`, `PermissionsBoundaryArn`).

### 3. Set the GitHub variables

These values are not secrets. A helper that reads one output of the stack:

```bash
out() { aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name be-power-forecast-bootstrap --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
```

```bash
gh variable set AWS_REGION --repo "$REPO" --body "$AWS_REGION"
```

```bash
gh variable set AWS_DEPLOY_ROLE_ARN --repo "$REPO" --body "$(out DeployRoleArn)"
```

```bash
gh variable set AWS_READONLY_ROLE_ARN --repo "$REPO" --body "$(out ReadOnlyRoleArn)"
```

```bash
gh variable set TF_STATE_BUCKET --repo "$REPO" --body "$(out StateBucket)"
```

```bash
gh variable set TF_LOCK_TABLE --repo "$REPO" --body "$(out LockTable)"
```

```bash
gh variable set DATA_BUCKET --repo "$REPO" --body "$(out DataBucket)"
```

```bash
gh variable set SITE_BUCKET --repo "$REPO" --body "$(out SiteBucket)"
```

Replace the address with the one that should receive the budget alerts:

```bash
gh variable set BUDGET_EMAIL --repo "$REPO" --body "name@example.com"
```

```bash
gh variable list --repo "$REPO"
```

Check: the eight variables are listed. The secrets `ENTSOE_API_KEY` (already there),
`DATABRICKS_HOST` and `DATABRICKS_TOKEN` (optional) are managed in GitHub only:

```bash
gh secret list --repo "$REPO"
```

With the variables set, the pull request can show its Terraform plan: re-run its checks
and read the summary of the `Deploy (AWS)` run.

```bash
gh run rerun "$(gh run list --repo "$REPO" --branch aws --workflow deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --repo "$REPO"
```

```bash
gh run watch "$(gh run list --repo "$REPO" --branch aws --workflow deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --repo "$REPO" --exit-status
```

Check: the run succeeds and its summary lists the resources to create (about 40).

### 4. Merge the pull request and deploy

Only after Julien's explicit approval of the pull request.

```bash
gh pr merge aws --repo "$REPO" --merge
```

```bash
gh run watch "$(gh run list --repo "$REPO" --branch main --workflow deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --repo "$REPO" --exit-status
```

Check: the run succeeds (about 10 minutes: the image is built, pushed, then applied); its
summary gives the page and API URLs. Then:

```bash
aws lambda get-function --region "$AWS_REGION" --function-name be-power-forecast-api --query 'Configuration.{state: State, update: LastUpdateStatus, image: ImageUri}'
```

Check: `Active`, `Successful`, and the image tag is the merge commit.

```bash
aws ecs describe-task-definition --region "$AWS_REGION" --task-definition be-power-forecast-live --query 'taskDefinition.{revision: revision, cpu: cpu, memory: memory, image: containerDefinitions[0].image}'
```

The deploy role is now used from GitHub only; the schedules exist from this point (a run
before step 6 stops at once: `state/` is empty).

### 5. Copy the ENTSO-E key to SSM

A `workflow_dispatch` workflow can only be run once it is on `main`, hence after step 4. It
writes the secret `ENTSOE_API_KEY` to SSM without printing it.

```bash
gh workflow run sync-secrets.yml --repo "$REPO"
```

```bash
gh run watch "$(gh run list --repo "$REPO" --workflow sync-secrets.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --repo "$REPO" --exit-status
```

```bash
aws ssm describe-parameters --region "$AWS_REGION" --parameter-filters Key=Name,Values=/be-power-forecast/entsoe-api-key --query 'Parameters[].{name: Name, type: Type, version: Version, modified: LastModifiedDate}'
```

Check: one `SecureString` parameter (its value is not shown).

### 6. Seed the S3 state

Copies the live files of `main` and the ENTSO-E cache of the former Actions workflow (so the
first run does not download 2015-2026 again). Run it soon after the merge: GitHub evicts a
cache unused for 7 days. It refuses to overwrite a `state/` that is not empty.

```bash
gh workflow run seed-state.yml --repo "$REPO"
```

```bash
gh run watch "$(gh run list --repo "$REPO" --workflow seed-state.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --repo "$REPO" --exit-status
```

```bash
aws s3 ls --recursive "s3://$(out DataBucket)/"
```

Check: `state/results/forecasts/live/forecasts.csv`, `dnn_forecasts.csv`,
`state/results/dnn/live/summary.csv`, `state/results/live/realised.csv`,
`state/live/README.md`, and the `*_live.parquet` and `*_2015-01-01_2026-09-30.parquet` files
under `cache/`. Without the cache (warning in the run), the first task downloads the full
history from ENTSO-E, which takes longer but works.

The same seeding without the workflow (state only), from an up-to-date checkout of `main`:

```bash
for dir in results/forecasts/live results/dnn/live results/live live; do aws s3 sync "$dir" "s3://$(out DataBucket)/state/$dir"; done
```

### 7. First run, then check the API and the page

```bash
VPC=$(aws ec2 describe-vpcs --region "$AWS_REGION" --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
```

```bash
SUBNETS=$(aws ec2 describe-subnets --region "$AWS_REGION" --filters Name=vpc-id,Values="$VPC" Name=default-for-az,Values=true --query 'Subnets[].SubnetId' --output text | tr '\t' ',')
```

```bash
SG=$(aws ec2 describe-security-groups --region "$AWS_REGION" --filters Name=vpc-id,Values="$VPC" Name=group-name,Values=default --query 'SecurityGroups[0].GroupId' --output text)
```

```bash
TASK=$(aws ecs run-task --region "$AWS_REGION" --cluster be-power-forecast --launch-type FARGATE --task-definition be-power-forecast-live --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=ENABLED}" --query 'tasks[0].taskArn' --output text) && echo "$TASK"
```

```bash
aws logs tail /ecs/be-power-forecast-live --region "$AWS_REGION" --follow
```

Stop following (Ctrl-C) once the log says `page published`. A full run takes 10 to 20
minutes (one to three when the day is already forecast). Then:

```bash
aws ecs describe-tasks --region "$AWS_REGION" --cluster be-power-forecast --tasks "$TASK" --query 'tasks[0].{status: lastStatus, exit: containers[0].exitCode, reason: stoppedReason}'
```

Check: `STOPPED`, exit code `0`. Exit code `2` means `state/` is empty (step 6). An
`OutOfMemoryError` reason means `task_memory` must grow.

```bash
API_URL=$(aws lambda get-function-url-config --region "$AWS_REGION" --function-name be-power-forecast-api --query FunctionUrl --output text) && echo "$API_URL"
```

```bash
curl -s "${API_URL}health"
```

Check: `"status": "ok"`, `"lear_forecasts": true`, `"prices": false` (no ENTSO-E prices on
Lambda, see above), and `last_day` is the last day forecast.

```bash
curl -s -X POST "${API_URL}forecast" -H 'Content-Type: application/json' -d "{\"delivery_day\": \"$(curl -s "${API_URL}health" | python3 -c 'import json, sys; print(json.load(sys.stdin)["last_day"])')\"}"
```

Check: `"model": "lear_ensemble"`, 24 `prices`, and 24 `dnn_prices` when the DNN ensemble
forecast that day.

```bash
PAGE_URL=https://$(aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='Live page of be-power-forecast'].DomainName" --output text)/ && echo "$PAGE_URL"
```

```bash
curl -sI "$PAGE_URL" | grep -iE '^(HTTP|content-type|cache-control)'
```

Check: `HTTP/2 200`, `text/html`, `max-age=300`; open the URL in a browser. A new
distribution can take a few minutes to answer everywhere.

```bash
curl -s -o /dev/null -w '%{http_code}\n' "https://$(out DataBucket).s3.$AWS_REGION.amazonaws.com/cache/prices_BE_live.parquet"
```

Check: `403`: the ENTSO-E data are not public.

Finally, put the two URLs in the README (and its template, which `make_report.py`
renders), on a branch and through a pull request:

```bash
git switch -c readme-aws-urls origin/main
```

```bash
sed -i '' -e "s#__LIVE_PAGE_URL__#$PAGE_URL#" -e "s#__API_URL__#$API_URL#" README.md docs/README.template.md
```

(On Linux: `sed -i` without `''`.)

```bash
git diff --stat && git commit -am "docs: link the live page and the API on AWS" && git push -u origin readme-aws-urls && gh pr create --repo "$REPO" --fill
```

From then on, the schedules run every evening; nothing else is needed. If AWS cannot run
a day, the fallback runs the same script on GitHub's runner:

```bash
gh workflow run live.yml --repo "$REPO"
```

### 8. Remove everything

Terraform must be the pinned version (1.16.6); on a Mac with Apple silicon:

```bash
curl -sSLo /tmp/terraform.zip https://releases.hashicorp.com/terraform/1.16.6/terraform_1.16.6_darwin_arm64.zip && unzip -o /tmp/terraform.zip terraform -d /tmp/terraform-1.16.6
```

```bash
/tmp/terraform-1.16.6/terraform -chdir=infra init -backend-config="bucket=$(out StateBucket)" -backend-config="dynamodb_table=$(out LockTable)"
```

(The backend warns that `dynamodb_table` is deprecated in favour of `use_lockfile`; it is
still supported, and the lock table is what this deployment uses.)

```bash
/tmp/terraform-1.16.6/terraform -chdir=infra destroy -var image_tag=destroy -var budget_email=name@example.com
```

Check: Terraform asks for `yes`, then removes about 40 resources (CloudFront takes up to
15 minutes); the buckets and the registry are emptied first. Then the parameter, which
Terraform does not manage:

```bash
aws ssm delete-parameter --region "$AWS_REGION" --name /be-power-forecast/entsoe-api-key
```

Then the bootstrap stack. Its state bucket is kept on deletion (it holds the state):
empty it and remove it after the stack.

```bash
STATE_BUCKET=$(out StateBucket) && echo "$STATE_BUCKET"
```

```bash
aws cloudformation delete-stack --region "$AWS_REGION" --stack-name be-power-forecast-bootstrap && aws cloudformation wait stack-delete-complete --region "$AWS_REGION" --stack-name be-power-forecast-bootstrap
```

```bash
aws s3api delete-objects --bucket "$STATE_BUCKET" --delete "$(aws s3api list-object-versions --bucket "$STATE_BUCKET" --query '{Objects: Versions[].{Key: Key, VersionId: VersionId}}' --output json)"
```

```bash
aws s3api delete-objects --bucket "$STATE_BUCKET" --delete "$(aws s3api list-object-versions --bucket "$STATE_BUCKET" --query '{Objects: DeleteMarkers[].{Key: Key, VersionId: VersionId}}' --output json)"
```

(This one fails harmlessly when there is no delete marker.)

```bash
aws s3api delete-bucket --bucket "$STATE_BUCKET"
```

```bash
for v in AWS_REGION AWS_DEPLOY_ROLE_ARN AWS_READONLY_ROLE_ARN TF_STATE_BUCKET TF_LOCK_TABLE DATA_BUCKET SITE_BUCKET BUDGET_EMAIL; do gh variable delete "$v" --repo "$REPO"; done
```

Check:

```bash
aws resourcegroupstaggingapi get-resources --region "$AWS_REGION" --tag-filters Key=Project,Values=be-power-forecast --query 'ResourceTagMappingList[].ResourceARN'
```

An empty list (the tag index can lag by a few minutes). The ECS service-linked role
`AWSServiceRoleForECS` stays; it is free.

## 9. Costs

Prices of `eu-west-1`, on a paid plan (on the free plan, they come out of the credits).

| Service | Use | Per month |
|---|---|---|
| ECS Fargate | ~20 min a day (full run 10-20 min, fallback 1-3 min), 2 vCPU and 8 GB: 0.117 $/h | ~1.20 $ |
| Public IPv4 of the task | while it runs, 0.005 $/h | ~0.05 $ |
| ECR | the last 5 images, ~1 GB each, layers shared in part, 0.10 $/GB | 0.10-0.40 $ |
| S3 | a few tens of MB, a few thousand requests | < 0.05 $ |
| Lambda | well inside the free 1 M requests and 400,000 GB-s | 0 $ |
| CloudFront | well inside the free 1 TB and 10 M requests | 0 $ |
| EventBridge Scheduler, SSM (standard), CloudWatch Logs (14 days), DynamoDB (on demand), Budgets | free tiers | 0 $ |
| **Total** | | **about 1.5 $** |

No NAT gateway (~32 $), load balancer, database or Secrets Manager. The budget alerts at
4 $ and 5 $. The API is public and without authentication: abnormal traffic would show in
the budget alerts first. Lowering `task_memory` back to 4 GB would save about 0.2 $, at the
risk described above.

## Security

* No AWS key exists for GitHub: the workflows get short-lived credentials through OIDC,
  for workflows of this repository only.
* The deploy role can only touch resources named `be-power-forecast*`; it can create roles
  only under `/be-power-forecast/` and only with the permissions boundary of the bootstrap
  stack, cannot remove that boundary or attach managed policies, so it cannot grant more
  than the workloads need.
* The read-only role of `sync-databricks.yml` can read `state/` and nothing else.
* Each workload role has its own minimal policy (`infra/iam.tf`); the API can only read
  `state/results/forecasts/live/`.
* The ENTSO-E key is a `SecureString` in SSM, copied from the GitHub secret by
  `sync-secrets.yml` and injected by ECS; it is never printed.
* Both buckets are private (public access blocked, owner-enforced, encrypted); CloudFront
  reads the site bucket through Origin Access Control.

## Databricks

`sync-databricks.yml` replaces the last step of the former `live.yml` with the same three
files and the same destination: `results/forecasts/live/forecasts.csv`,
`results/forecasts/live/dnn_forecasts.csv` and `results/live/realised.csv`, copied to
`dbfs:/Volumes/workspace/be_power/live/` with `databricks fs cp --overwrite`. It runs at
18:15 and 21:15 UTC (45 minutes after each run on AWS) and by hand, reads the files from
`state/` with the read-only role, and succeeds without copying anything when
`DATABRICKS_HOST` or `DATABRICKS_TOKEN` is not set.

```bash
gh workflow run sync-databricks.yml --repo "$REPO"
```
