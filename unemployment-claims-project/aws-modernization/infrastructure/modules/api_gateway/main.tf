##############################################################################
# API Gateway + Cognito Module
# REST API with JWT authorization replacing SYSIN batch input
##############################################################################

variable "environment" { type = string }
variable "lambda_get_invoke_arn" { type = string }
variable "lambda_create_invoke_arn" { type = string }
variable "lambda_update_invoke_arn" { type = string }
variable "lambda_delete_invoke_arn" { type = string }
variable "lambda_report_invoke_arn" { type = string }
variable "lambda_get_function_name" { type = string }
variable "lambda_create_function_name" { type = string }
variable "lambda_update_function_name" { type = string }
variable "lambda_delete_function_name" { type = string }
variable "lambda_report_function_name" { type = string }

# --- Cognito User Pool (replaces missing COBOL auth) ---

resource "aws_cognito_user_pool" "main" {
  name = "claims-${var.environment}"

  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
  }

  mfa_configuration = "ON"

  software_token_mfa_configuration {
    enabled = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  schema {
    name                = "role"
    attribute_data_type = "String"
    mutable             = true

    string_attribute_constraints {
      max_length = 50
    }
  }

  tags = { Name = "claims-${var.environment}" }
}

resource "aws_cognito_user_pool_client" "main" {
  name         = "claims-api-${var.environment}"
  user_pool_id = aws_cognito_user_pool.main.id

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity  = 1  # hours
  id_token_validity      = 1
  refresh_token_validity = 30 # days
}

# Role groups (R20: role-based write access)
resource "aws_cognito_user_group" "reader" {
  name         = "claims_reader"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Read-only access to claims data"
}

resource "aws_cognito_user_group" "writer" {
  name         = "claims_writer"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Read and write access to claims data"
}

resource "aws_cognito_user_group" "admin" {
  name         = "claims_admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Full administrative access including delete"
}

# --- API Gateway ---

resource "aws_api_gateway_rest_api" "main" {
  name        = "claims-api-${var.environment}"
  description = "Unemployment Claims REST API - replaces COBOL SYSIN batch interface"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# Cognito authorizer
resource "aws_api_gateway_authorizer" "cognito" {
  name            = "cognito-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.main.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [aws_cognito_user_pool.main.arn]
  identity_source = "method.request.header.Authorization"
}

# --- /claims resource ---

resource "aws_api_gateway_resource" "claims" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "claims"
}

resource "aws_api_gateway_resource" "claims_by_key" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.claims.id
  path_part   = "{period_key}"
}

# GET /claims (range query)
resource "aws_api_gateway_method" "get_claims" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.claims.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id

  request_parameters = {
    "method.request.querystring.start"    = false
    "method.request.querystring.count"    = false
    "method.request.querystring.category" = false
  }
}

resource "aws_api_gateway_integration" "get_claims" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.claims.id
  http_method             = aws_api_gateway_method.get_claims.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_get_invoke_arn
}

# GET /claims/{period_key} (single record)
resource "aws_api_gateway_method" "get_claim_by_key" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.claims_by_key.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_claim_by_key" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.claims_by_key.id
  http_method             = aws_api_gateway_method.get_claim_by_key.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_get_invoke_arn
}

# POST /claims (create)
resource "aws_api_gateway_method" "create_claim" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.claims.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "create_claim" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.claims.id
  http_method             = aws_api_gateway_method.create_claim.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_create_invoke_arn
}

# PUT /claims/{period_key} (update)
resource "aws_api_gateway_method" "update_claim" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.claims_by_key.id
  http_method   = "PUT"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "update_claim" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.claims_by_key.id
  http_method             = aws_api_gateway_method.update_claim.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_update_invoke_arn
}

# DELETE /claims/{period_key} (soft delete)
resource "aws_api_gateway_method" "delete_claim" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.claims_by_key.id
  http_method   = "DELETE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "delete_claim" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.claims_by_key.id
  http_method             = aws_api_gateway_method.delete_claim.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_delete_invoke_arn
}

# --- /reports resource ---

resource "aws_api_gateway_resource" "reports" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "reports"
}

resource "aws_api_gateway_resource" "reports_generate" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.reports.id
  path_part   = "generate"
}

resource "aws_api_gateway_method" "generate_report" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.reports_generate.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "generate_report" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.reports_generate.id
  http_method             = aws_api_gateway_method.generate_report.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_report_invoke_arn
}

# --- Lambda Permissions ---

resource "aws_lambda_permission" "api_gateway" {
  for_each = {
    get_claims    = var.lambda_get_function_name
    create_claim  = var.lambda_create_function_name
    update_claim  = var.lambda_update_function_name
    delete_claim  = var.lambda_delete_function_name
    report        = var.lambda_report_function_name
  }

  statement_id  = "AllowAPIGateway-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = each.value
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# --- Deployment ---

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  depends_on = [
    aws_api_gateway_integration.get_claims,
    aws_api_gateway_integration.get_claim_by_key,
    aws_api_gateway_integration.create_claim,
    aws_api_gateway_integration.update_claim,
    aws_api_gateway_integration.delete_claim,
    aws_api_gateway_integration.generate_report,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment
}

# --- Outputs ---

output "api_url" {
  value = aws_api_gateway_stage.main.invoke_url
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.main.id
}
