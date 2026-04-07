##############################################################################
# Lambda Module
# 7 Lambda functions replacing GETCLAIM.cbl CRUD + validation + reporting
##############################################################################

variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "db_secret_arn" { type = string }
variable "db_host" { type = string }
variable "db_port" { type = number }
variable "db_name" { type = string }
variable "report_bucket_name" { type = string }

# --- Security Group ---

resource "aws_security_group" "lambda" {
  name_prefix = "claims-lambda-"
  vpc_id      = var.vpc_id
  description = "Lambda functions - outbound to Aurora/RDS Proxy and AWS services"

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "PostgreSQL to RDS Proxy"
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS to AWS services (Secrets Manager, S3, etc.)"
  }

  tags = { Name = "claims-lambda-${var.environment}" }
}

# --- IAM Role ---

resource "aws_iam_role" "lambda" {
  name = "claims-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda_vpc" {
  name = "vpc-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_secrets" {
  name = "secrets-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.db_secret_arn]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "arn:aws:logs:*:*:*"
    }]
  })
}

# --- S3 Report Bucket ---

resource "aws_s3_bucket" "reports" {
  bucket = var.report_bucket_name
  tags   = { Name = "claims-reports-${var.environment}" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "s3-reports"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:PutObject", "s3:GetObject"]
      Resource = ["${aws_s3_bucket.reports.arn}/*"]
    }]
  })
}

# --- Common environment variables ---

locals {
  lambda_env = {
    DB_HOST      = var.db_host
    DB_PORT      = tostring(var.db_port)
    DB_NAME      = var.db_name
    DB_SECRET_ARN = var.db_secret_arn
    ENVIRONMENT  = var.environment
  }

  functions = {
    claims_get = {
      handler     = "handler.handler"
      source_dir  = "${path.module}/../../../services/claims_get"
      description = "Get claims by key or range (replaces GETCLAIM R command)"
      timeout     = 30
      memory      = 256
    }
    claims_create = {
      handler     = "handler.handler"
      source_dir  = "${path.module}/../../../services/claims_create"
      description = "Create claim record (replaces GETCLAIM I command)"
      timeout     = 30
      memory      = 256
    }
    claims_update = {
      handler     = "handler.handler"
      source_dir  = "${path.module}/../../../services/claims_update"
      description = "Update claim with temporal versioning (replaces GETCLAIM U command)"
      timeout     = 30
      memory      = 256
    }
    claims_delete = {
      handler     = "handler.handler"
      source_dir  = "${path.module}/../../../services/claims_delete"
      description = "Soft-delete claim (replaces GETCLAIM D command)"
      timeout     = 30
      memory      = 256
    }
    claims_validate = {
      handler     = "handler.handler"
      source_dir  = "${path.module}/../../../services/claims_validate"
      description = "OPA policy validation for all business rules (R01-R20)"
      timeout     = 10
      memory      = 128
    }
    claims_report = {
      handler     = "handler.handler"
      source_dir  = "${path.module}/../../../services/claims_report"
      description = "Report generation (replaces UNEMPCLM OUTCLAIM writer)"
      timeout     = 60
      memory      = 512
    }
  }
}

# --- Lambda Functions ---

data "archive_file" "lambda" {
  for_each = local.functions

  type        = "zip"
  source_dir  = each.value.source_dir
  output_path = "${path.module}/dist/${each.key}.zip"
}

resource "aws_lambda_function" "main" {
  for_each = local.functions

  function_name    = "claims-${each.key}-${var.environment}"
  role             = aws_iam_role.lambda.arn
  handler          = each.value.handler
  runtime          = "python3.11"
  timeout          = each.value.timeout
  memory_size      = each.value.memory
  filename         = data.archive_file.lambda[each.key].output_path
  source_code_hash = data.archive_file.lambda[each.key].output_base64sha256
  description      = each.value.description

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = local.lambda_env
  }

  layers = [aws_lambda_layer_version.shared.arn]
}

# --- Shared Lambda Layer (db.py, models.py, dependencies) ---

data "archive_file" "shared_layer" {
  type        = "zip"
  source_dir  = "${path.module}/../../../services/shared"
  output_path = "${path.module}/dist/shared_layer.zip"
}

resource "aws_lambda_layer_version" "shared" {
  layer_name          = "claims-shared-${var.environment}"
  filename            = data.archive_file.shared_layer.output_path
  source_code_hash    = data.archive_file.shared_layer.output_base64sha256
  compatible_runtimes = ["python3.11"]
  description         = "Shared DB connection, models, and validation utilities"
}

# --- CloudWatch Log Groups ---

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.functions

  name              = "/aws/lambda/claims-${each.key}-${var.environment}"
  retention_in_days = 90
}

# --- Outputs ---

output "security_group_id" {
  value = aws_security_group.lambda.id
}

output "get_invoke_arn" {
  value = aws_lambda_function.main["claims_get"].invoke_arn
}

output "create_invoke_arn" {
  value = aws_lambda_function.main["claims_create"].invoke_arn
}

output "update_invoke_arn" {
  value = aws_lambda_function.main["claims_update"].invoke_arn
}

output "delete_invoke_arn" {
  value = aws_lambda_function.main["claims_delete"].invoke_arn
}

output "report_invoke_arn" {
  value = aws_lambda_function.main["claims_report"].invoke_arn
}

output "get_function_name" {
  value = aws_lambda_function.main["claims_get"].function_name
}

output "create_function_name" {
  value = aws_lambda_function.main["claims_create"].function_name
}

output "update_function_name" {
  value = aws_lambda_function.main["claims_update"].function_name
}

output "delete_function_name" {
  value = aws_lambda_function.main["claims_delete"].function_name
}

output "report_function_name" {
  value = aws_lambda_function.main["claims_report"].function_name
}

output "report_bucket_name" {
  value = aws_s3_bucket.reports.id
}
