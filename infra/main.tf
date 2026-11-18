# Production deployment of the live forecast (docs/aws.md):
# * ECR: one image for the live forecast and the API;
# * S3: a private data bucket (cache/: ENTSO-E and SMARD downloads; state/: the live files
#   of the repository) and a private site bucket behind CloudFront (the live page);
# * ECS Fargate, run every evening by EventBridge Scheduler (scripts/aws_run.py), in the
#   default VPC with a public IP (no NAT gateway);
# * Lambda with a private function URL (signed requests): the forecast service (api/app.py);
# * a monthly budget with e-mail alerts.
# The IAM roles live under the path /be-power-forecast/ with the permissions boundary of
# the bootstrap stack, the only roles the deploy role may create.

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  name       = "be-power-forecast"
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  data_bucket          = "${local.name}-data-${local.account_id}"
  site_bucket          = "${local.name}-site-${local.account_id}"
  api_function         = "${local.name}-api"
  live_family          = "${local.name}-live"
  role_path            = "/${local.name}/"
  permissions_boundary = "arn:${local.partition}:iam::${local.account_id}:policy/${local.name}-boundary"
  entsoe_parameter     = "/${local.name}/entsoe-api-key"
  entsoe_parameter_arn = "arn:${local.partition}:ssm:${var.region}:${local.account_id}:parameter${local.entsoe_parameter}"
  image                = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
}
