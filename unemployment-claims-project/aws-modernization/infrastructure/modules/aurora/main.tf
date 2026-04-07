##############################################################################
# Aurora PostgreSQL Module
# Multi-AZ cluster with RDS Proxy, KMS encryption, and Secrets Manager
##############################################################################

variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "lambda_security_group_id" { type = string }
variable "db_instance_class" { type = string }
variable "db_name" { type = string }

# --- KMS Key for encryption at rest ---

resource "aws_kms_key" "aurora" {
  description             = "Claims Aurora encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = { Name = "claims-aurora-${var.environment}" }
}

# --- Secrets Manager for DB credentials ---

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "claims-db-credentials-${var.environment}"
  description = "Aurora PostgreSQL credentials for claims system"
  kms_key_id  = aws_kms_key.aurora.arn
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "claims_admin"
    password = random_password.db_password.result
    host     = aws_rds_cluster.main.endpoint
    port     = 5432
    dbname   = var.db_name
  })
}

# --- Security Groups ---

resource "aws_security_group" "aurora" {
  name_prefix = "claims-aurora-"
  vpc_id      = var.vpc_id
  description = "Aurora PostgreSQL cluster - accepts connections from Lambda/RDS Proxy only"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.lambda_security_group_id, aws_security_group.rds_proxy.id]
    description     = "PostgreSQL from Lambda and RDS Proxy"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "claims-aurora-${var.environment}" }
}

resource "aws_security_group" "rds_proxy" {
  name_prefix = "claims-rds-proxy-"
  vpc_id      = var.vpc_id
  description = "RDS Proxy - connection pooling between Lambda and Aurora"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.lambda_security_group_id]
    description     = "PostgreSQL from Lambda"
  }

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [aws_security_group.aurora.id]
    description = "PostgreSQL to Aurora"
  }

  tags = { Name = "claims-rds-proxy-${var.environment}" }
}

# --- Subnet Group ---

resource "aws_db_subnet_group" "main" {
  name       = "claims-${var.environment}"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "claims-${var.environment}" }
}

# --- Aurora Cluster ---

resource "aws_rds_cluster" "main" {
  cluster_identifier     = "claims-${var.environment}"
  engine                 = "aurora-postgresql"
  engine_version         = "15.4"
  database_name          = var.db_name
  master_username        = "claims_admin"
  master_password        = random_password.db_password.result
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  storage_encrypted      = true
  kms_key_id             = aws_kms_key.aurora.arn

  backup_retention_period = 35
  preferred_backup_window = "03:00-04:00"
  skip_final_snapshot     = var.environment != "prod"

  tags = { Name = "claims-${var.environment}" }
}

resource "aws_rds_cluster_instance" "writer" {
  identifier         = "claims-writer-${var.environment}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.db_instance_class
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
}

resource "aws_rds_cluster_instance" "reader" {
  identifier         = "claims-reader-${var.environment}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.db_instance_class
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
}

# --- RDS Proxy ---

resource "aws_iam_role" "rds_proxy" {
  name = "claims-rds-proxy-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "rds.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "rds_proxy_secrets" {
  name = "secrets-access"
  role = aws_iam_role.rds_proxy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.db_credentials.arn]
    }]
  })
}

resource "aws_db_proxy" "main" {
  name                   = "claims-${var.environment}"
  engine_family          = "POSTGRESQL"
  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_subnet_ids         = var.private_subnet_ids
  vpc_security_group_ids = [aws_security_group.rds_proxy.id]
  require_tls            = true

  auth {
    auth_scheme = "SECRETS"
    iam_auth    = "DISABLED"
    secret_arn  = aws_secretsmanager_secret.db_credentials.arn
  }
}

resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name

  connection_pool_config {
    max_connections_percent = 80
    max_idle_connections_percent = 50
    connection_borrow_timeout = 120
  }
}

resource "aws_db_proxy_target" "main" {
  db_proxy_name          = aws_db_proxy.main.name
  target_group_name      = aws_db_proxy_default_target_group.main.name
  db_cluster_identifier  = aws_rds_cluster.main.id
}

# --- Outputs ---

output "cluster_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

output "reader_endpoint" {
  value = aws_rds_cluster.main.reader_endpoint
}

output "rds_proxy_endpoint" {
  value = aws_db_proxy.main.endpoint
}

output "db_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
}
