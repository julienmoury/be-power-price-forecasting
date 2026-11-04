output "api_url" {
  description = "Public URL of the forecast service (GET /health, POST /forecast, GET /forecasts)."
  value       = aws_lambda_function_url.api.function_url
}

output "page_url" {
  description = "Public live page."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}/"
}

output "data_bucket" {
  value = aws_s3_bucket.data.bucket
}

output "site_bucket" {
  value = aws_s3_bucket.site.bucket
}

output "ecr_repository" {
  value = aws_ecr_repository.app.repository_url
}

output "image_tag" {
  description = "Image deployed by the last apply."
  value       = var.image_tag
}

output "run_task" {
  description = "Command that runs the live forecast once, as the schedules do."
  value = join(" ", [
    "aws ecs run-task --region ${var.region} --cluster ${aws_ecs_cluster.live.name}",
    "--launch-type FARGATE --task-definition ${aws_ecs_task_definition.live.family}",
    "--network-configuration 'awsvpcConfiguration={subnets=[${join(",", data.aws_subnets.default.ids)}],securityGroups=[${data.aws_security_group.default.id}],assignPublicIp=ENABLED}'",
  ])
}
