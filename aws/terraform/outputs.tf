output "https_url" {
  description = "AWS-provided HTTPS URL for the clinic application."
  value       = "https://${aws_cloudfront_distribution.clinic.domain_name}"
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.clinic.name
}

output "api_service_name" {
  value = var.enable_services ? aws_ecs_service.api[0].name : null
}

output "ui_service_name" {
  value = var.enable_services ? aws_ecs_service.ui[0].name : null
}

output "api_ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ui_ecr_repository_url" {
  value = aws_ecr_repository.ui.repository_url
}

output "database_host" {
  value = aws_db_instance.clinic.address
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.clinic.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.clinic.id
}

output "init_task_definition_arn" {
  value = var.enable_services ? aws_ecs_task_definition.init[0].arn : null
}

output "task_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "task_security_group_id" {
  value = aws_security_group.ecs.id
}
