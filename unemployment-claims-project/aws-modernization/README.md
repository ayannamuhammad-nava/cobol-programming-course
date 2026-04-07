# Unemployment Claims System - AWS Modernization

## Overview

This project modernizes the legacy COBOL-based unemployment claims system (UNEMPCLM.cbl + GETCLAIM.cbl + VSAM CLAIMS) into a cloud-native AWS architecture following the **Phased Decoupling (Strangler Fig)** strategy recommended in the [Modernization Report](../output/COBOL_AWS_Modernization_Report.txt).

## Architecture Summary

```
HTTP/Batch Input
       |
  API Gateway + Cognito JWT Auth
       |
  OPA Policy Validation (Lambda)
       |
  Step Functions Orchestrator
       |
  +----+----+----+----+
  |    |    |    |    |
 Get Create Update Delete  GenerateReport
  |    |    |    |    |
  Aurora PostgreSQL (Multi-AZ, KMS Encrypted)
       |
  Output: QuickSight / PDF / Athena
```

## Directory Structure

```
aws-modernization/
├── README.md                  # This file
├── architecture.md            # High-level architecture and design decisions
├── services/                  # Lambda microservices (Python)
│   ├── claims_get/            # GetByKey and GetRange operations
│   │   └── handler.py
│   ├── claims_create/         # Create (Insert) operation
│   │   └── handler.py
│   ├── claims_update/         # Update operation
│   │   └── handler.py
│   ├── claims_delete/         # Delete operation
│   │   └── handler.py
│   ├── claims_validate/       # OPA policy validation
│   │   └── handler.py
│   ├── claims_report/         # Report generation (PDF)
│   │   └── handler.py
│   ├── shared/                # Shared utilities
│   │   ├── db.py              # Aurora connection pooling via RDS Proxy
│   │   └── models.py          # Data models and validation
│   └── requirements.txt       # Python dependencies
├── infrastructure/            # Terraform IaC
│   ├── main.tf                # Root module
│   ├── variables.tf           # Input variables
│   ├── outputs.tf             # Stack outputs
│   ├── modules/
│   │   ├── vpc/               # VPC, subnets, security groups
│   │   │   └── main.tf
│   │   ├── aurora/            # Aurora PostgreSQL cluster
│   │   │   └── main.tf
│   │   ├── lambda/            # Lambda functions + IAM roles
│   │   │   └── main.tf
│   │   └── api_gateway/       # API Gateway + Cognito
│   │       └── main.tf
│   └── environments/
│       ├── dev.tfvars
│       └── prod.tfvars
├── api/                       # API contract
│   └── openapi.yaml           # OpenAPI 3.0 specification
└── data/                      # Data layer
    ├── schema.sql             # Aurora PostgreSQL schema
    ├── seed.sql               # Sample data (from OUTCLAIM.txt)
    └── migration.md           # VSAM-to-Aurora migration approach
```

## Migration Phases

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| **1. Stabilize** | 1-4 | Git baseline, VSAM export, data dictionary |
| **2. Decouple** | 5-12 | Aurora schema loaded, nightly sync running |
| **3. Refactor** | 13-24 | Lambda, API Gateway, Step Functions, OPA policies |
| **4. Validate** | 25-30 | 6-week parallel run, UAT sign-off |
| **5. Cut Over** | 31+ | Production cutover, 90-day stabilization |

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.5
- Python >= 3.11
- Docker (for local Lambda testing)

### Deploy Infrastructure

```bash
cd infrastructure
terraform init
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

### Run Database Migration

```bash
psql -h <aurora-endpoint> -U claims_admin -d unemployment_claims -f data/schema.sql
psql -h <aurora-endpoint> -U claims_admin -d unemployment_claims -f data/seed.sql
```

### Deploy Lambda Functions

```bash
cd services
pip install -r requirements.txt -t package/
# Package and deploy each function via Terraform or SAM CLI
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Aurora PostgreSQL over DynamoDB | Claims data is relational (period-to-counts is one-to-many); requires joins and aggregates |
| Step Functions over pure Lambda | Workflow has sequential steps with state; built-in retry and execution history |
| OPA policy engine on Lambda | Business rules independently deployable and testable by non-developers |
| SQS for batch ingestion | Decouples ingestion from processing; replaces SYSIN 200-command hard limit |
| Temporal schema | Regulatory data requires amendment history; VSAM REWRITE destroyed prior values |
| RDS Proxy | Pools Lambda connections to prevent Aurora exhaustion during peak batch |

## Business Rules Coverage

All 12 existing rules (R01-R12) are preserved. The 6 missing rules (R15-R20) are implemented for the first time:

- **R15**: Cross-category totals validation (age = race = gender)
- **R16**: Valid MMDDYYYY period key format
- **R17**: Non-negative claim counts
- **R18**: Realistic count ceiling with alerting
- **R19**: INA counts included in totals
- **R20**: Role-based write access enforcement
