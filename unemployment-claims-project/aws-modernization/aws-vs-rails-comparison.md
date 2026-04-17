# AWS App vs Rails App — Full Comparison

This document compares the AWS modernized app (Python Lambda microservices on AWS infrastructure) to the Rails sandbox app. Both implement the same unemployment claims system, but with very different architectures.

---

## Architecture Overview

```
AWS App:
  Browser/API Client
       │
  API Gateway + Cognito JWT
       │
  OPA Validation Lambda
       │
  Step Functions Orchestrator
       │
  ┌────┴────┬────────┬────────┬──────────┐
  Get    Create   Update   Delete    Report
  Lambda  Lambda   Lambda   Lambda   Lambda
       │
  RDS Proxy
       │
  Aurora PostgreSQL (Multi-AZ)
       │
  S3 / QuickSight / Athena / SNS


Rails App:
  Browser
       │
  Rails Router (config/routes.rb)
       │
  Pundit Authorization
       │
  ┌────┴────────────────┐
  ClaimsController    AuditLogsController    ReportsController
       │
  ActiveRecord Models (validations)
       │
  PostgreSQL 14 (Docker container)
```

---

## AWS Service to Rails Mapping

| AWS Service | What it does in AWS App | Rails Equivalent | Gap |
|---|---|---|---|
| **API Gateway** | Routes HTTP requests to Lambda functions | `config/routes.rb` | Rails routes are simpler but equivalent for basic routing |
| **Cognito** | User authentication, JWT tokens, MFA, user roles | Devise (mock mode) | No MFA, no real user roles, no JWT tokens |
| **OPA on Lambda** | Externalized business rules as .rego policy files | Model validations in Ruby | Rules are embedded in code, not independently deployable |
| **Step Functions** | Orchestrates multi-step operations with retry and error handling | `ActiveRecord::Base.transaction` | No retry logic, no dead-letter queue, no execution history |
| **Lambda (x6)** | 6 separate functions for get, create, update, delete, validate, report | 3 Rails controllers | Same logic, different structure (microservices vs monolith) |
| **Aurora PostgreSQL** | Managed database, Multi-AZ, automatic failover, read replicas | PostgreSQL 14 in Docker | No failover, no read replicas, single container |
| **RDS Proxy** | Connection pooling for Lambda burst traffic | Puma thread pool | Rails manages connections differently, no burst concern |
| **S3** | File storage for reports, bulk CSV uploads, batch ingestion | Not implemented | No file storage, no batch uploads |
| **SQS** | Message queue for batch processing (replaces COBOL 200-command limit) | Not implemented | No message queue, no batch processing |
| **EventBridge** | Scheduled jobs (nightly R15 integrity checks, report generation) | Not implemented | No scheduled jobs |
| **SNS** | Alert notifications on validation failures | Not implemented | No alerting |
| **CloudWatch** | Metrics, alarms, structured JSON logging | Rails.logger | Basic logging only, no metrics or alarms |
| **CloudTrail** | Immutable API-level access log | claim_audit_logs table | Rails audit is application-level, not infrastructure-level |
| **KMS** | Encryption at rest for all data | Not implemented | No encryption (local development) |
| **Secrets Manager** | Auto-rotating database credentials | .env file | Password is static, stored in plain text |
| **VPC** | Network isolation (public/private subnets) | Docker network | No network segmentation |
| **QuickSight** | Interactive dashboards | claims_reports/show view | Static HTML table vs interactive dashboard |
| **Athena** | Ad-hoc SQL queries on S3 Parquet exports | Not implemented | No data export or ad-hoc query tool |
| **Terraform** | Infrastructure as code (deploy/destroy entire stack) | Docker Compose + Makefile | Docker Compose is local only, not cloud deployable |
| **OpenAPI spec** | API contract defined in openapi.yaml | No API spec | Rails is a web UI, not a documented API |

---

## Compute Comparison

| Aspect | AWS App | Rails App |
|---|---|---|
| **Runtime** | Python 3.11 on AWS Lambda | Ruby 3.4.5 on Puma (in Docker) |
| **Architecture** | 6 microservices (one Lambda per operation) | 1 monolith (3 controllers in one app) |
| **Scaling** | Auto-scales per Lambda function independently | Single container, no auto-scaling |
| **Cold start** | Lambda cold start delay (~1-3 seconds first request) | Always running, no cold start |
| **Concurrency** | Each Lambda handles one request at a time, scales out to hundreds | Puma handles multiple requests with threads |
| **Cost when idle** | $0 (Lambda only charges when running) | Docker container runs continuously |
| **Memory** | 256MB per Lambda function | Shared container memory |

---

## Database Comparison

| Aspect | AWS App | Rails App |
|---|---|---|
| **Engine** | Aurora PostgreSQL 15.4 | PostgreSQL 14 |
| **Hosting** | AWS managed (Multi-AZ) | Docker container on localhost |
| **Failover** | Automatic (< 30 seconds) | None |
| **Read replicas** | Yes (serves QuickSight dashboards) | None |
| **Connection pooling** | RDS Proxy | Rails connection pool |
| **Encryption at rest** | KMS customer-managed key | None |
| **Encryption in transit** | TLS 1.3 required (sslmode=require) | None (local connection) |
| **Backups** | Continuous, 35-day retention | None (volume persists between restarts) |
| **Credentials** | AWS Secrets Manager (auto-rotating) | .env file (static password) |
| **CHECK constraints** | R16 (period_key format), R17 (non-negative), R18 (ceiling) | None (validated in Ruby only) |
| **SQL View** | v_cross_category_totals for R15 | None (calculated in Ruby) |
| **Data access** | Raw SQL with psycopg2 | ActiveRecord ORM |
| **Row locking** | FOR UPDATE on reads before writes | None |
| **Cost** | ~$162/month (Aurora + RDS Proxy) | Free (Docker) |

---

## Security Comparison

| Security Layer | AWS App | Rails App |
|---|---|---|
| **Authentication** | Cognito User Pools with MFA for admins | Devise with mock adapter (any email/password) |
| **Authorization** | Cognito Groups + OPA policy engine (reader/writer/admin roles) | Pundit policies (allows all logged-in users everything) |
| **Role-based access (R20)** | Yes — claims_reader, claims_writer, claims_admin | Not implemented |
| **Encryption at rest** | AWS KMS (customer-managed key) on Aurora + S3 | None |
| **Encryption in transit** | TLS 1.3 on all connections | None (localhost) |
| **Network isolation** | VPC with public/private subnet separation | Docker network (no segmentation) |
| **Secrets management** | AWS Secrets Manager with auto-rotation | .env file with static password |
| **API-level audit** | CloudTrail (immutable, AWS-managed) | None |
| **Application audit** | claim_audit_log table with SHA-256 hashes | claim_audit_logs table with SHA-256 hashes |
| **Infrastructure compliance** | AWS Config Rules | None |
| **CSRF protection** | Not needed (API with JWT tokens) | Rails built-in CSRF tokens |
| **XSS protection** | Not needed (no HTML output) | Rails built-in HTML escaping |

---

## Business Rules Comparison

| Rule | Description | AWS App | Rails App |
|---|---|---|---|
| R01 | Valid operation code | API Gateway + OPA | Not needed (HTTP methods) |
| R02 | Record count > 0 | OPA | Not needed (routing) |
| R03/R04 | Valid category for range | OPA | Not implemented |
| R05 | Record exists before delete | Delete Lambda (FOR UPDATE) | Partial (RecordNotFound, no row lock) |
| R06 | Record exists before update | Update Lambda (FOR UPDATE) | Partial (no row lock) |
| R07 | Read-back on create | Create Lambda | Not implemented |
| R08 | Read-back on update | Update Lambda | Not implemented |
| R09 | No duplicates | Create Lambda + DB constraint | **Yes** (model + DB unique index) |
| R12 | Audit every write | All write Lambdas | **Yes** (ClaimsController) |
| R15 | Cross-category totals | OPA + models.py + SQL view | **Yes** (model validation) |
| R16 | Period key format | OPA + models.py + DB CHECK | **Yes** (model validation, no DB CHECK) |
| R17 | Non-negative counts | OPA + models.py + DB CHECK | **Yes** (model validation, no DB CHECK) |
| R18 | Count ceiling (10M) | OPA + models.py + DB CHECK | **Yes** (model validation, no DB CHECK) |
| R19 | INA counts present | OPA (warning) | Not implemented |
| R20 | Role-based write access | Cognito + OPA | Not implemented |

**AWS enforces rules at 3 levels:** API Gateway schema → OPA Lambda → Database CHECK constraints

**Rails enforces rules at 1 level:** Model validations only

---

## Ingestion & Processing Comparison

| Capability | AWS App | Rails App |
|---|---|---|
| **HTTP API** | API Gateway REST endpoints (JSON in/out) | Web forms (HTML in, HTML out) |
| **Batch file upload** | S3 upload → SQS → Lambda pipeline | Not supported |
| **Scheduled processing** | EventBridge cron → Step Functions | Not supported |
| **Message queuing** | SQS (unlimited, durable) | Not supported |
| **Retry on failure** | Step Functions exponential backoff | None (user resubmits form) |
| **Dead-letter queue** | SQS DLQ for failed operations | None |
| **Execution history** | Step Functions records every execution | None |
| **Concurrent processing** | Lambda scales to hundreds of parallel executions | Single Puma server |

---

## Output & Reporting Comparison

| Output | AWS App | Rails App |
|---|---|---|
| **Interactive dashboards** | Amazon QuickSight | claims_reports/show.html.erb (static HTML table) |
| **PDF reports** | Lambda PDF generator → S3 pre-signed URL | Not implemented |
| **JSON reports** | Lambda → S3 with download URL | Not implemented |
| **Text reports (OUTCLAIM.txt)** | Lambda text formatter | Not implemented |
| **Ad-hoc SQL queries** | Amazon Athena on S3 Parquet exports | Not implemented |
| **Integrity alerts** | EventBridge → SNS email/SMS | Not implemented |
| **R15 validation display** | QuickSight dashboard | PASS/FAIL tags in HTML table |
| **Audit trail view** | CloudTrail + application audit log | claim_audit_logs/index.html.erb with filters |

---

## Infrastructure & Deployment Comparison

| Aspect | AWS App | Rails App |
|---|---|---|
| **Infrastructure definition** | Terraform (HCL) | docker-compose.yml |
| **Deployment target** | AWS cloud (us-east-1) | localhost:3100 |
| **Environments** | dev.tfvars, prod.tfvars | Single .env file |
| **Deploy command** | `terraform apply -var-file=environments/dev.tfvars` | `make start-container` |
| **Destroy command** | `terraform destroy` | `docker compose down -v` |
| **State management** | S3 backend with DynamoDB locking | None needed |
| **Availability zones** | 2 AZs (us-east-1a, us-east-1b) | Single machine |
| **Auto-scaling** | Lambda auto-scales, Aurora read replicas | None |
| **Load balancing** | API Gateway handles distribution | None |
| **CI/CD** | Can integrate with CodePipeline/GitHub Actions | None |

---

## Cost Comparison

| | AWS App (Dev) | Rails App |
|---|---|---|
| Aurora PostgreSQL | ~$140/month | Free (Docker) |
| RDS Proxy | ~$22/month | N/A |
| Lambda (x7) | ~$5/month | N/A |
| API Gateway | ~$4/month | N/A |
| Step Functions | ~$2/month | N/A |
| CloudWatch | ~$10/month | N/A |
| S3 | ~$1/month | N/A |
| Cognito | Free tier | N/A |
| SQS | Free tier | N/A |
| Docker/Colima | N/A | Free |
| **Total** | **~$184/month** | **$0/month** |

Production AWS costs would be significantly higher with larger Aurora instances, more Lambda invocations, and QuickSight licensing.

---

## Disaster Recovery Comparison

| Metric | AWS App | Rails App |
|---|---|---|
| **RPO (data loss window)** | < 5 minutes (Aurora continuous backup) | All data lost if volume deleted |
| **RTO (recovery time)** | < 30 minutes (Multi-AZ failover + Terraform redeploy) | `make init-container` (rebuild from scratch) |
| **Backup retention** | 35 days (Aurora automated backups) | None |
| **Cross-region recovery** | Optional (Aurora Global Database) | Not possible |
| **Data recovery** | Point-in-time restore to any second within 35 days | Re-run seeds (only seed data recoverable) |

---

## What Rails Has That AWS Doesn't

| # | Feature | Details |
|---|---|---|
| 1 | **Full web UI** | 7 USWDS-styled screens — AWS is API-only |
| 2 | **Sign up / sign in pages** | Visual auth flow — AWS uses JWT tokens programmatically |
| 3 | **Inline form validation** | Error messages next to fields — AWS returns JSON errors |
| 4 | **Audit trail filter UI** | Filter by period/operation in browser |
| 5 | **Delete confirmation dialog** | Browser prompt before deleting |
| 6 | **Navigation bar** | "Claims" link in header |
| 7 | **Temporal versioning notice** | Edit page explains what happens on update |
| 8 | **JSONB details on audit log** | Extra metadata field |
| 9 | **i18n support** | Routes support Spanish locale prefix (/es-us/claims) |
| 10 | **Zero cost** | Runs free on your laptop |

---

## What AWS Has That Rails Doesn't

| # | Category | Feature |
|---|---|---|
| 1 | **Rules** | R01-R04 (command validation) |
| 2 | **Rules** | R05/R06 (existence check with row locking) |
| 3 | **Rules** | R07/R08 (read-back confirmation) |
| 4 | **Rules** | R19 (INA counts warning) |
| 5 | **Rules** | R20 (role-based write access) |
| 6 | **Security** | MFA for admin roles |
| 7 | **Security** | Cognito user roles (reader/writer/admin) |
| 8 | **Security** | KMS encryption at rest |
| 9 | **Security** | TLS 1.3 encryption in transit |
| 10 | **Security** | VPC network isolation |
| 11 | **Security** | Secrets Manager auto-rotating credentials |
| 12 | **Security** | AWS Config compliance rules |
| 13 | **Database** | CHECK constraints (R16, R17, R18 at DB level) |
| 14 | **Database** | SQL view for R15 validation |
| 15 | **Database** | FOR UPDATE row locking |
| 16 | **Database** | Multi-AZ failover |
| 17 | **Database** | Read replicas |
| 18 | **Database** | Continuous backups (35-day retention) |
| 19 | **Database** | NAICS code on industry categories |
| 20 | **Database** | Category versioning (effective_from/to) |
| 21 | **Processing** | Batch file upload via S3 |
| 22 | **Processing** | SQS message queue |
| 23 | **Processing** | EventBridge scheduled jobs |
| 24 | **Processing** | Step Functions orchestration with retry/DLQ |
| 25 | **Reporting** | PDF report generation |
| 26 | **Reporting** | JSON/text report download via S3 pre-signed URL |
| 27 | **Reporting** | QuickSight interactive dashboards |
| 28 | **Reporting** | Athena ad-hoc SQL queries |
| 29 | **Reporting** | SNS failure alerts |
| 30 | **Observability** | CloudWatch metrics and alarms |
| 31 | **Observability** | CloudTrail API audit |
| 32 | **Observability** | Structured JSON logging with correlation IDs |
| 33 | **Observability** | Nightly R15 integrity check |
| 34 | **Infra** | Terraform infrastructure as code |
| 35 | **Infra** | Multi-environment support (dev/prod) |
| 36 | **Infra** | OpenAPI 3.0 API specification |

---

## Summary

| Metric | AWS App | Rails App |
|---|---|---|
| **Total AWS services used** | 14 | 0 |
| **Business rules** | 20 (R01-R20) | 5 (R09, R15-R18) |
| **Features AWS has that Rails doesn't** | 36 | — |
| **Features Rails has that AWS doesn't** | — | 10 |
| **Monthly cost** | ~$184 (dev) | $0 |
| **Setup time** | Terraform apply (~15 min) | make init-container (~5 min) |
| **Production ready?** | Yes (with proper AWS account) | No (local development only) |
| **Has a UI?** | No (API only) | Yes (7 screens) |

**Bottom line:** The AWS app is built for production — secure, scalable, observable, and compliant. The Rails app is built for usability — visual, interactive, and free to run locally. The core claims logic (CRUD, temporal versioning, audit trail, key validations) exists in both.
