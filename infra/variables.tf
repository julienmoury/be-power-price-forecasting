variable "region" {
  description = "AWS region of every resource."
  type        = string
  default     = "eu-central-1"
}

variable "image_tag" {
  description = "Tag of the image in ECR (the commit SHA, set by .github/workflows/deploy.yml)."
  type        = string
}

variable "budget_email" {
  description = "E-mail address of the budget alerts (GitHub variable BUDGET_EMAIL)."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_email))
    error_message = "budget_email must be an e-mail address."
  }
}

variable "budget_usd" {
  description = "Monthly budget, in USD; alerts at 80 % and 100 %."
  type        = number
  default     = 5
}

variable "task_cpu" {
  description = "vCPU of the live forecast task, in CPU units (1024 = 1 vCPU)."
  type        = number
  default     = 2048
}

variable "task_memory" {
  description = <<-EOT
    Memory of the live forecast task, in MiB. 8 GB rather than 4: the four DNNs train in
    parallel, each process with its own TensorFlow and input window (docs/aws.md).
  EOT
  type        = number
  default     = 8192
}

variable "schedules" {
  description = "Daily runs of the live forecast (UTC); the second one is a fallback."
  type        = map(string)
  default = {
    "1730" = "cron(30 17 * * ? *)"
    "2030" = "cron(30 20 * * ? *)"
  }
}

variable "log_retention_days" {
  description = "Retention of the CloudWatch logs."
  type        = number
  default     = 14
}
