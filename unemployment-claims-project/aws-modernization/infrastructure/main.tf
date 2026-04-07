##############################################################################
# Unemployment Claims System - AWS Infrastructure
# Root Terraform module orchestrating all components
##############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "unemployment-claims-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-lock"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "unemployment-claims"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ---------- Networking ----------

module "vpc" {
  source = "./modules/vpc"

  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

# ---------- Database ----------

module "aurora" {
  source = "./modules/aurora"

  environment          = var.environment
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  lambda_security_group_id = module.lambda.security_group_id
  db_instance_class    = var.db_instance_class
  db_name              = "unemployment_claims"
}

# ---------- Lambda Functions ----------

module "lambda" {
  source = "./modules/lambda"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  db_secret_arn      = module.aurora.db_secret_arn
  db_host            = module.aurora.rds_proxy_endpoint
  db_port            = 5432
  db_name            = "unemployment_claims"
  report_bucket_name = "unemployment-claims-reports-${var.environment}"
}

# ---------- API Gateway + Auth ----------

module "api_gateway" {
  source = "./modules/api_gateway"

  environment              = var.environment
  lambda_get_invoke_arn    = module.lambda.get_invoke_arn
  lambda_create_invoke_arn = module.lambda.create_invoke_arn
  lambda_update_invoke_arn = module.lambda.update_invoke_arn
  lambda_delete_invoke_arn = module.lambda.delete_invoke_arn
  lambda_report_invoke_arn = module.lambda.report_invoke_arn
  lambda_get_function_name    = module.lambda.get_function_name
  lambda_create_function_name = module.lambda.create_function_name
  lambda_update_function_name = module.lambda.update_function_name
  lambda_delete_function_name = module.lambda.delete_function_name
  lambda_report_function_name = module.lambda.report_function_name
}
