output "ecr_repository_url" {
  value = aws_ecr_repository.runtime.repository_url
}

output "gha_role_arn" {
  value = aws_iam_role.gha.arn
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "rds_address" {
  value = aws_db_instance.main.address
}

output "app_url" {
  value = "https://${local.domain}"
}
