# Forecast service (api/app.py, unchanged) on Lambda, from the same image, behind the AWS
# Lambda Web Adapter (Dockerfile). At start, python -m be_power_forecast.cloud copies the
# live forecasts of state/ to /tmp. The ENTSO-E prices are not given to Lambda
# (BE_PRICE_PATH points to no file): no naive fallback, as when the file is missing locally.
# Reserved concurrency is left unset (a new account may be limited to 10 in total).

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.api_function}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "api" {
  function_name = local.api_function
  description   = "Belgian day-ahead price forecast service"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = local.image
  architectures = ["x86_64"]
  memory_size   = 2048
  timeout       = 60 # a cold start can take over 30 s, see docs/aws.md

  image_config {
    command = ["python", "-m", "be_power_forecast.cloud"]
  }

  environment {
    variables = {
      PORT                         = "8080"
      AWS_LWA_PORT                 = "8080"
      AWS_LWA_READINESS_CHECK_PATH = "/health"
      BE_DATA_BUCKET               = aws_s3_bucket.data.bucket
      BE_API_DIR                   = "/tmp/api"
      BE_PRICE_PATH                = "/tmp/no-entsoe-prices.parquet"
      # Past the 10 s init window, keep starting during the first request instead of
      # letting Lambda restart the init from scratch.
      AWS_LWA_ASYNC_INIT = "true"
      # Changed by scripts/aws_run.py after each new forecast, so that Lambda starts new
      # execution environments, which read the new files.
      BE_STATE_VERSION = "deploy"
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.api.name
  }

  lifecycle {
    ignore_changes = [environment[0].variables["BE_STATE_VERSION"]]
  }
}

# Private function URL: AWS signs and checks each request (SigV4) before Lambda runs, so
# an unsigned or unauthorised call is refused without invoking the function. Callers are
# principals of this account allowed by their own IAM policy (docs/aws.md, "Calling the
# API"); no resource-based permission is granted to anyone else.
resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "AWS_IAM"
}
