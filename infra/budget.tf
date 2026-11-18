resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Actual spend at 80 % and 100 %, and a forecast above 100 % (an early warning: the
  # billing data reach Budgets with several hours of delay).
  dynamic "notification" {
    for_each = { actual_80 = [80, "ACTUAL"], actual_100 = [100, "ACTUAL"], forecast_100 = [100, "FORECASTED"] }
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value[0]
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value[1]
      subscriber_email_addresses = [var.budget_email]
    }
  }
}
