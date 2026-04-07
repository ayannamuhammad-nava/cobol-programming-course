output "api_gateway_url" {
  description = "Base URL for the Claims REST API"
  value       = module.api_gateway.api_url
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID for authentication"
  value       = module.api_gateway.cognito_user_pool_id
}

output "cognito_client_id" {
  description = "Cognito App Client ID"
  value       = module.api_gateway.cognito_client_id
}

output "aurora_cluster_endpoint" {
  description = "Aurora cluster writer endpoint"
  value       = module.aurora.cluster_endpoint
}

output "aurora_reader_endpoint" {
  description = "Aurora cluster reader endpoint"
  value       = module.aurora.reader_endpoint
}

output "rds_proxy_endpoint" {
  description = "RDS Proxy endpoint for Lambda connections"
  value       = module.aurora.rds_proxy_endpoint
}

output "report_bucket" {
  description = "S3 bucket for generated reports"
  value       = module.lambda.report_bucket_name
}
