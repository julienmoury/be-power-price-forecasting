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
  timeout       = 30

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

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"

  # Any site may read the forecasts (the service has no write endpoint; POST /forecast is a
  # query), without credentials.
  cors {
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_headers     = ["content-type"]
    allow_credentials = false
    max_age           = 86400
  }
}

# A public function URL needs both permissions.
resource "aws_lambda_permission" "url" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invoke" {
  statement_id             = "FunctionURLAllowInvokeAction"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.api.function_name
  principal                = "*"
  invoked_via_function_url = true
}
