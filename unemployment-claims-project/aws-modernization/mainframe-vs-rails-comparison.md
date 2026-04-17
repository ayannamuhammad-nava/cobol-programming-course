# Mainframe (Python/AWS) vs Rails App — Full Comparison

This document provides a detailed comparison between the modernized mainframe app (Python Lambda/AWS) and the Rails sandbox app after integration.

---

## Features In the Mainframe App That Are MISSING From Rails

| # | Feature | Mainframe App | Rails App |
|---|---|---|---|
| 1 | **R01: Valid operation code validation** | Validates R/I/U/D operation codes | Not needed — Rails uses HTTP methods (GET/POST/PATCH/DELETE) instead |
| 2 | **R02: Record count > 0 validation** | Validates num_records >= 1 | Not needed — Rails handles this through routing |
| 3 | **R03/R04: Valid category for range queries** | Validates category on range queries | No range query with category filter exists |
| 4 | **R05: Record must exist before delete** | Explicit check with error response | Rails will raise RecordNotFound but doesn't return a clean 404 page |
| 5 | **R06: Record must exist before update** | Explicit check with FOR UPDATE row lock | No row-level locking on update — could have race conditions |
| 6 | **R07: Read-back confirmation on create** | Reads back the record after insert to verify | Not implemented |
| 7 | **R08: Read-back confirmation on update** | Reads back the record after update to verify | Not implemented |
| 8 | **R19: INA counts present (warning)** | Warns if no INA (not applicable) fields submitted | Not implemented |
| 9 | **R20: Role-based write access** | Validates user has claims_writer or claims_admin role | Pundit allows all logged-in users to do everything |
| 10 | **Range query with category filter** | GET /claims?start=01011900&count=10&category=age | Index page shows all claims but no filtering by category |
| 11 | **Report generation to S3** | Generates PDF/JSON/text reports, uploads to S3 with pre-signed URL | Report is view-only in the browser, no downloadable file |
| 12 | **Text report format (OUTCLAIM.txt style)** | Generates formatted text matching original COBOL output | Not implemented |
| 13 | **S3 file upload for batch ingestion** | S3 upload triggers processing pipeline | Not implemented |
| 14 | **SQS message queue for batch processing** | Replaces COBOL SYSIN 200-command limit | Not implemented — web UI only |
| 15 | **EventBridge scheduled jobs** | Nightly integrity checks, scheduled report generation | Not implemented |
| 16 | **Step Functions orchestration** | State machine with retry, error handling, DLQ | Rails uses simple database transactions |
| 17 | **OPA policy engine** | Externalized business rules as .rego files | Validations are in Ruby model code |
| 18 | **OpenAPI 3.0 specification** | Full API contract defined in openapi.yaml | No API spec — it's a web UI, not an API |
| 19 | **FOR UPDATE row locking** | Prevents concurrent updates to same record | Not implemented — possible race condition |
| 20 | **Deleted counts returned in response** | DELETE response includes all 43 count values for recovery | Soft delete only, counts not shown in response |
| 21 | **Database CHECK constraints** | chk_count_non_negative, chk_count_ceiling in SQL | Relies on Rails model validations only (not enforced at DB level) |
| 22 | **v_cross_category_totals database view** | SQL view for quick R15 validation queries | Calculated in Ruby code each time |
| 23 | **naics_code on category reference** | Industry categories have NAICS code field | Not present |
| 24 | **effective_from/effective_to on categories** | Categories support OMB SPD-15 updates over time | Categories are static (no versioning) |
| 25 | **SNS alerting on failures** | Sends notifications on validation failures | No alerting |
| 26 | **CloudWatch observability** | Metrics, alarms, structured JSON logging | No observability beyond Rails logs |
| 27 | **Multi-AZ deployment** | Aurora cluster across 2 availability zones | Single Docker container on localhost |
| 28 | **KMS encryption at rest** | All data encrypted with customer-managed key | No encryption (local development) |
| 29 | **Secrets Manager for credentials** | DB password rotated automatically | Password hardcoded in .env file |

---

## Features In Rails That Are NEW (Not In Mainframe App)

| # | Feature | Rails App | Mainframe App |
|---|---|---|---|
| 1 | **Full web UI** | 7 USWDS-styled screens with forms, tables, navigation | API-only (no UI, just JSON responses) |
| 2 | **User authentication UI** | Sign up / sign in pages with Devise | Cognito JWT tokens (no UI) |
| 3 | **Inline form validation errors** | Error messages shown next to each field | Errors returned as JSON array |
| 4 | **Audit trail filtering UI** | Filter by period key and operation type in browser | No UI for viewing audit trail |
| 5 | **Report dashboard in browser** | Summary table with R15 status for all periods | Report was a downloadable file |
| 6 | **Navigation bar** | "Claims" link in the app header | No navigation (API endpoints) |
| 7 | **Delete confirmation dialog** | Browser prompt before deleting | No confirmation (API call deletes immediately) |
| 8 | **Temporal versioning notice** | Edit page shows info alert about versioning | No UI to explain what happens |
| 9 | **JSONB details field on audit log** | Stores additional metadata as JSON | Not present |
| 10 | **i18n support (internationalization)** | Routes support locale prefixes (e.g., /es-us/claims) | English only |

---

## Structural Differences

| Aspect | Mainframe App (Python/AWS) | Rails App |
|---|---|---|
| **Language** | Python 3.11 | Ruby 3.4.5 |
| **Architecture** | Microservices (6 separate Lambda functions) | Monolith (3 controllers in one app) |
| **Database** | Aurora PostgreSQL (AWS managed) | PostgreSQL 14 (Docker container) |
| **Auth** | AWS Cognito with JWT tokens | Devise with mock adapter |
| **Authorization** | OPA policy engine + Cognito roles | Pundit policies (allows everything) |
| **Data access** | Raw SQL with psycopg2 | ActiveRecord ORM |
| **Count storage** | category_type + category_code columns per row | demographic_category_id foreign key per row |
| **Infrastructure** | Terraform (VPC, Lambda, API Gateway, Aurora) | Docker Compose (2 containers) |
| **Deployment** | AWS (multi-AZ, auto-scaling) | localhost:3100 |
| **API contract** | OpenAPI 3.0 spec | No API (web forms) |
| **Batch processing** | SQS + S3 + EventBridge | Not supported |
| **Business rules** | 20 rules (R01-R20) | 5 rules (R09, R15-R18) |

---

## Business Rules Comparison

| Rule | Description | Mainframe App | Rails App |
|---|---|---|---|
| R01 | Valid operation code (R/I/U/D) | Yes | Not needed (HTTP methods) |
| R02 | Record count > 0 | Yes | Not needed (routing) |
| R03/R04 | Valid category for range queries | Yes | Not implemented |
| R05 | Record must exist before delete | Yes | Partial (no clean 404) |
| R06 | Record must exist before update (with row lock) | Yes | Partial (no row lock) |
| R07 | Read-back confirmation on create | Yes | Not implemented |
| R08 | Read-back confirmation on update | Yes | Not implemented |
| R09 | No duplicate current records | Yes | **Yes** |
| R12 | Audit log every write | Yes | **Yes** |
| R15 | Cross-category totals match (age = race = gender) | Yes | **Yes** |
| R16 | Period key format (MMDDYYYY, DD=01) | Yes | **Yes** |
| R17 | Non-negative counts | Yes | **Yes** |
| R18 | Realistic count ceiling (10M) | Yes | **Yes** |
| R19 | INA counts present (warning) | Yes | Not implemented |
| R20 | Role-based write access | Yes | Not implemented |

---

## Database Schema Differences

| Aspect | Mainframe App | Rails App |
|---|---|---|
| **claims_period table** | Has CHECK constraint on period_key format (R16) | No CHECK constraint (validated in Ruby only) |
| **claim_demographic_counts** | Has CHECK constraints for R17 and R18 | No CHECK constraints (validated in Ruby only) |
| **claim_demographic_counts** | Uses category_type + category_code columns | Uses demographic_category_id foreign key |
| **demographic_category_ref** | Has naics_code column for industry NAICS codes | No naics_code column |
| **demographic_category_ref** | Has effective_from/effective_to for category versioning | No category versioning |
| **claim_audit_log** | Has CHECK constraint on operation values | No CHECK constraint (validated in Ruby only) |
| **claim_audit_log** | No details column | Has JSONB details column for extra metadata |
| **SQL View** | v_cross_category_totals view for R15 queries | No view (calculated in Ruby) |
| **Primary keys** | UUID (generated in Python) | UUID (generated by Rails) |

---

## Summary

| Metric | Mainframe App | Rails App |
|---|---|---|
| **Total features** | API + infrastructure + batch + observability | Web UI + CRUD + audit |
| **Business rules enforced** | 20 (R01-R20) | 5 (R09, R15-R18) |
| **Missing from Rails** | 29 features | — |
| **New in Rails** | — | 10 features |
| **Core CRUD** | Yes | Yes |
| **Temporal versioning** | Yes | Yes |
| **Soft delete** | Yes | Yes |
| **Audit trail** | Yes | Yes |
| **Web UI** | No | Yes |

The **core business logic** (CRUD operations, temporal versioning, soft delete, audit trail, R15/R16/R17/R18 validations) is present in both apps.

The mainframe app has more **infrastructure, security, and operational features** (encryption, alerting, row locking, batch processing, API spec) suited for production AWS deployment.

The Rails app has a **full web interface** that the mainframe app lacks, making it usable by non-technical users through a browser.
