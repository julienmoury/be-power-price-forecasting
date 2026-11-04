# Live forecast: an ECS Fargate task (scripts/aws_run.py), run by EventBridge Scheduler at
# the times of the former GitHub Actions crons. Default VPC, public subnet and public IP:
# the task only calls out (ENTSO-E, SMARD, S3, ECR) and a NAT gateway would cost ~32 $/month.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# The default security group of the default VPC: all outbound traffic, inbound only from
# itself (nothing else uses it here).
data "aws_security_group" "default" {
  vpc_id = data.aws_vpc.default.id
  name   = "default"
}

resource "aws_ecs_cluster" "live" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_cloudwatch_log_group" "live" {
  name              = "/ecs/${local.live_family}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_task_definition" "live" {
  family                   = local.live_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "live"
    image     = local.image
    essential = true
    command   = ["python", "scripts/aws_run.py"]
    environment = [
      { name = "BE_DATA_BUCKET", value = aws_s3_bucket.data.bucket },
      { name = "BE_SITE_BUCKET", value = aws_s3_bucket.site.bucket },
      { name = "BE_API_FUNCTION", value = local.api_function },
      { name = "BE_WORK_DIR", value = "/tmp/work" },
      { name = "GIT_COMMIT", value = var.image_tag },
    ]
    # Written by .github/workflows/sync-secrets.yml from the GitHub secret ENTSOE_API_KEY.
    secrets = [{ name = "ENTSOE_API_KEY", valueFrom = local.entsoe_parameter_arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.live.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "live"
      }
    }
  }])
}

resource "aws_scheduler_schedule" "live" {
  for_each = var.schedules

  name                         = "${local.live_family}-${each.key}"
  description                  = "Daily live forecast (scripts/aws_run.py)"
  schedule_expression          = each.value
  schedule_expression_timezone = "UTC"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.live.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.live.arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        assign_public_ip = true
        subnets          = data.aws_subnets.default.ids
        security_groups  = [data.aws_security_group.default.id]
      }
    }

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
}
