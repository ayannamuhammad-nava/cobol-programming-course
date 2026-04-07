# Architecture Design Document

## Unemployment Claims System - AWS Target State

### 1. System Context

The unemployment claims system processes monthly aggregate demographic data for unemployment insurance filings. It supports CRUD operations on filing period records and generates statistical reports broken down by age, ethnicity, industry, race, and gender.

**Current State**: Two COBOL programs (UNEMPCLM.cbl orchestrator + GETCLAIM.cbl data layer) operating on a VSAM KSDS file on IBM z/OS.

**Target State**: Cloud-native microservices on AWS with REST API, event-driven batch processing, policy-as-code validation, and temporal data model.

---

### 2. Architecture Layers

#### 2.1 Ingestion Layer

```
HTTP Clients ──> API Gateway (REST) ──> Cognito JWT Authorizer
Batch Files  ──> S3 Upload Event   ──> SQS (claims-command-queue)
Scheduled    ──> EventBridge Cron  ──> Step Functions
```

- **API Gateway** exposes RESTful endpoints for all claim operations
- **Amazon Cognito** authenticates users and issues JWT tokens with role claims
- **SQS** replaces the SYSIN 200-command batch limit with unlimited, durable message queuing
- **S3** accepts bulk CSV/JSON uploads that trigger processing pipelines
- **EventBridge** schedules recurring jobs (nightly integrity checks, report generation)

#### 2.2 Policy Layer (OPA on Lambda)

All business rules are externalized into an Open Policy Agent engine running as a Lambda function. Rules are defined as `.rego` policy files, versioned in Git, and evaluated before every write operation.

| Rule | Description | Enforcement Point |
|------|-------------|-------------------|
| R01 | Valid operation codes only (R/I/U/D) | API Gateway request validation |
| R02 | Record count > 0 | API Gateway request validation |
| R03-R04 | Valid demographic category for range queries | OPA pre-execution |
| R15 | Cross-category totals: sum(age) = sum(race) = sum(gender) | OPA pre-write validation |
| R16 | Valid MMDDYYYY period key with day=01 | OpenAPI schema + OPA |
| R17 | Non-negative integer claim counts | OpenAPI schema + OPA |
| R18 | Realistic count ceiling (configurable threshold) | OPA with alerting |
| R19 | INA counts included in totals | OPA post-validation |
| R20 | Role-based write authorization | Cognito groups + OPA |

#### 2.3 Orchestration Layer (AWS Step Functions)

Replaces the UNEMPCLM.cbl batch loop. Each claim operation is a state machine:

```
StartExecution
    │
    ▼
ValidateInput (OPA Lambda)
    │
    ├── FAIL ──> DLQ + SNS Alert
    │
    ▼
RouteOperation
    │
    ├── GET_BY_KEY ──> GetClaim Lambda
    ├── GET_RANGE  ──> GetClaim Lambda (range mode)
    ├── CREATE     ──> CreateClaim Lambda
    ├── UPDATE     ──> UpdateClaim Lambda ──> ReadBack Lambda
    ├── DELETE     ──> DeleteClaim Lambda (capture-before-delete)
    │
    ▼
AuditLog Lambda
    │
    ▼
FormatResponse
```

**Key improvements over COBOL**:
- Each step is independently retryable with exponential backoff
- Execution history is permanently recorded
- Failed executions land in a dead-letter queue for investigation
- No 200-command batch limit

#### 2.4 Data Layer (Amazon Aurora PostgreSQL)

**Why PostgreSQL over DynamoDB**: Claims data is inherently relational. A single filing period has counts across 5 demographic categories with 43+ sub-categories. Aggregation queries (sum by category, cross-period trends) require SQL joins. DynamoDB would require extensive denormalization and GSIs that add cost without benefit.

**Schema Design Principles**:
- **Normalized**: Period metadata separated from demographic counts
- **Temporal**: Every record version is preserved with `effective_from`/`effective_to` timestamps. No UPDATE in place -- only INSERT new versions. This fixes the VSAM REWRITE data loss problem.
- **Extensible**: Demographic categories stored in a reference table, not hardcoded columns. Supports OMB SPD-15 (2024) 7-race categories without code changes.
- **INTEGER columns**: Replaces COBOL PIC X(05) that overflows at 99,999. PostgreSQL INTEGER supports values up to 2,147,483,647.

```
claims_period ──1:N──> claim_demographic_counts
                              │
                              └── FK to demographic_category_ref

claims_period ──1:N──> claim_audit_log
```

**Connection Management**: RDS Proxy sits between Lambda functions and Aurora, pooling connections to prevent exhaustion during burst processing.

**Multi-AZ Deployment**: Aurora cluster spans two AZs with automatic failover. Read replicas serve QuickSight dashboards.

#### 2.5 Output Layer

| Output | Replaces | Service |
|--------|----------|---------|
| Interactive dashboards | OUTCLAIM.txt manual review | Amazon QuickSight |
| PDF reports | OUTCLAIM.txt formatted print | Lambda PDF generator -> S3 pre-signed URL |
| Ad-hoc SQL queries | N/A (not possible in COBOL) | Amazon Athena on S3 Parquet exports |
| Integrity failure alerts | N/A (not possible in COBOL) | EventBridge -> SNS |

#### 2.6 Observability

- **CloudWatch Metrics**: Lambda duration/errors, API Gateway 4xx/5xx rates, Aurora connections/IOPS
- **CloudWatch Alarms**: Error rate > 1%, Lambda duration > 10s, Aurora CPU > 80%
- **CloudTrail**: Immutable API-level access log for all AWS service calls
- **Structured Logging**: JSON logs from all Lambda functions with correlation IDs
- **Nightly Integrity Check**: EventBridge-triggered Lambda runs R15 cross-totals validation across all periods

---

### 3. Security Architecture

| Layer | Control | AWS Service |
|-------|---------|-------------|
| Identity | User authentication with MFA for admin roles | Amazon Cognito User Pools |
| Authorization | Role-based access (reader/writer/admin) enforced before Lambda | Cognito Groups + API Gateway Authorizer + OPA |
| Encryption at rest | All Aurora data and S3 objects encrypted | AWS KMS (Customer Managed Key) |
| Encryption in transit | TLS 1.3 on all connections | API Gateway + RDS SSL |
| Audit logging | Immutable audit record for every write | Aurora `claim_audit_log` + CloudTrail |
| Network isolation | Aurora and Lambda in private subnets | VPC with public/private subnet separation |
| Secrets management | DB credentials rotated automatically | AWS Secrets Manager |
| Infrastructure compliance | Resource configs validated against policy | AWS Config Rules |

---

### 4. Deployment Architecture

```
                    ┌─────────────────────────────────┐
                    │          Public Subnet           │
                    │  ┌───────────────────────────┐   │
                    │  │     API Gateway (REST)     │   │
                    │  │   + Cognito Authorizer     │   │
                    │  └───────────┬───────────────┘   │
                    └──────────────┼───────────────────┘
                                   │
                    ┌──────────────┼───────────────────┐
                    │          Private Subnet A         │
                    │  ┌───────────┴───────────────┐   │
                    │  │    Lambda Functions (x7)    │   │
                    │  │    Step Functions Engine    │   │
                    │  │    SQS Consumer             │   │
                    │  └───────────┬───────────────┘   │
                    │              │                    │
                    │  ┌───────────┴───────────────┐   │
                    │  │       RDS Proxy            │   │
                    │  └───────────┬───────────────┘   │
                    └──────────────┼───────────────────┘
                                   │
                    ┌──────────────┼───────────────────┐
                    │          Private Subnet B         │
                    │  ┌───────────┴───────────────┐   │
                    │  │  Aurora PostgreSQL Cluster  │   │
                    │  │  (Primary + Read Replica)   │   │
                    │  └───────────────────────────┘   │
                    └──────────────────────────────────┘
```

---

### 5. Cost Estimate (Monthly - Dev Environment)

| Service | Configuration | Est. Monthly Cost |
|---------|---------------|-------------------|
| Aurora PostgreSQL | db.t4g.medium, Multi-AZ | ~$140 |
| Lambda (x7) | 256MB, ~100K invocations/month | ~$5 |
| API Gateway | ~100K requests/month | ~$4 |
| Step Functions | ~50K state transitions/month | ~$2 |
| Cognito | <1000 MAU | Free tier |
| S3 | <10GB storage | ~$1 |
| SQS | <1M messages/month | Free tier |
| RDS Proxy | 1 instance | ~$22 |
| CloudWatch | Standard metrics + logs | ~$10 |
| **Total** | | **~$184/month** |

Production costs will be higher due to larger Aurora instances, increased invocation volume, and QuickSight licensing.

---

### 6. Disaster Recovery

| Metric | Target | Implementation |
|--------|--------|----------------|
| RPO (Recovery Point Objective) | < 5 minutes | Aurora continuous backup + S3 versioning |
| RTO (Recovery Time Objective) | < 30 minutes | Multi-AZ failover + infrastructure-as-code redeploy |
| Backup retention | 35 days | Aurora automated backups |
| Cross-region | Optional | Aurora Global Database if required |
