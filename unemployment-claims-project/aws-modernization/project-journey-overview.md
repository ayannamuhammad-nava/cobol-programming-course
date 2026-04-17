# Project Journey: COBOL Mainframe to Rails Web Application

## Overview

This document captures the complete journey of taking a legacy COBOL mainframe unemployment claims system and getting it running as a modern web application inside a Ruby on Rails sandbox app with Docker.

---

## Complete Timeline (22 Steps)

Every step in the exact order they were executed:

| Step | What I did |
**Steps done before Claude Code**
| 1 | Install Nava Platform CLI - Install UV 
| 2 | uv tool install git+https://github.com/navapbc/platform-cli
| 3 | create sandbox - nava-platform app install --template-uri https://github.com/navapbc/template-application-rails . yoursandbox
| 4 | Check readme.md in sandbox
| 5 | create .env 
**Here is where I started using Claude Code from yoursandbox**
| 6 | Verified `.env` file existed | Checked that app config was ready |
| 7 | Installed Docker CLI | `brew install docker-compose` |
| 8 | Configured Docker plugin path | Updated `~/.docker/config.json` |
| 9 | Installed Docker runtime | `brew install colima` |
| 10 | Started Docker engine | `colima start` |
| 11 | Built Rails app + set up database | `make init-container` |
| 12 | Tell claude the location of your app
**Next Steps were based on my application**
| 13 | Created 4 database migrations | `docker compose run --rm ayannasandbox bin/rails generate migration ...` (x4) |
| 14 | Ran migrations to create tables | `docker compose run --rm ayannasandbox bin/rails db:migrate` |
| 15 | Created 4 model files | Wrote Ruby files with business rule validations |
| 16 | Created 3 controller files | Wrote Ruby files for CRUD, audit, reports |
| 17 | Created 2 Pundit policy files | Authorization rules for claims and audit logs |
| 18 | Created 7 view files | USWDS-styled HTML templates for all screens |
| 19 | Updated routes | Added claim routes to `config/routes.rb` |
| 20 | Updated navigation | Added "Claims" link to app header |
| 21 | Created seed file + ran seeds | `docker compose run --rm ayannasandbox bin/rails db:seed` |
This step runs the application and you can go to the hosting URL to view and test
| 22 | Launched the app | `make start-container` → http://localhost:3100 |

**Important:** 
Steps 1 - 5 done before Claude Code
Steps 6 - 22 done with Claude Code
Steps 10 and 22 need to run the application 

---

## Part 1: Setting Up the Development Docker Environment (Steps 1-7)

**Goal:** Get Docker and the Rails sandbox app running on macOS.

| Step | What we did | Why |
|---|---|---|
| 1 | Installed Docker CLI (`brew install docker`) | The tool that talks to containers |
| 2 | Verified `.env` file existed | App configuration (database password, auth mode, etc.) |
| 3 | Installed Docker Compose (`brew install docker-compose`) | Manages multi-container apps (Rails + PostgreSQL) |
| 4 | Configured Docker plugin path (`~/.docker/config.json`) | Told Docker where to find the Compose plugin |
| 5 | Installed Colima (`brew install colima`) | The runtime engine that actually runs containers on macOS |
| 6 | Started Colima (`colima start`) | Turned on the Docker engine |
| 7 | Ran `make init-container` | Built the Docker image, created the database, ran initial migrations and seeds |

**Result:** Rails sandbox app fully set up, database ready, but NOT launched yet.

---

## Part 2: Reading the Mainframe App (Step 8)

**Goal:** Understand the existing COBOL unemployment claims system and its AWS modernization so we could rewrite it in Rails.

**This step happened AFTER `init-container` and BEFORE any Rails code was written.**

We did NOT copy files from the mainframe app into the sandbox. Instead, we READ the source code to understand the business logic, then REWROTE it in Rails from scratch.

### How we accessed the code

You provided the path:
```
/Users/ayannamuhammad/cobol-programming-course-main/aws-unemployment-claims-analysis/unemployment-claims-project/aws-modernization/
```

### Files we read and what we learned

| File we read | What we learned from it |
|---|---|
| `README.md` | Overall architecture, directory structure, migration phases |
| `architecture.md` | Detailed design — all 6 layers, security, cost, disaster recovery |
| `services/shared/models.py` | **Most important file** — business rules (R15-R18), the 42 demographic categories, validation logic, data structures |
| `data/seed.sql` | The actual January 2017 data values from COBOL OUTCLAIM.txt, database schema |
| `demo/demo.py` | How CRUD operations work end-to-end |
| `demo/DEMO_INSTRUCTIONS.md` | How the local demo was set up |
| `demo/docker-compose.yml` | Database configuration |

### What the original COBOL system did
- Two programs: `UNEMPCLM.cbl` (orchestrator) + `GETCLAIM.cbl` (data layer)
- Ran on IBM z/OS mainframe
- Stored data in VSAM KSDS files
- Processed monthly unemployment claims with demographic breakdowns (age, race, gender, ethnicity, industry)
- Supported CRUD operations via batch commands (R/I/U/D)
- Had 12 business rules (R01-R12)
- Output to `OUTCLAIM.txt`

### What the AWS modernization already built (in Python)
- Python Lambda microservices replacing COBOL programs
- Aurora PostgreSQL replacing VSAM files
- API Gateway + Cognito for authentication
- Step Functions for orchestration
- Terraform for infrastructure
- 6 new business rules (R15-R20) the COBOL system never had
- A local demo using SQLite

### What we translated from Python to Rails

From `models.py`:
- `PERIOD_KEY_PATTERN` regex → Rails `ClaimsPeriod` model validation (R16)
- `MAX_CLAIM_COUNT = 10_000_000` → Rails `ClaimDemographicCount` validation (R18)
- `DEMOGRAPHIC_CATEGORIES` dictionary → `demographic_categories` database table + seed data
- `validate()` method with R15 logic → `cross_category_totals_match` custom validation
- `period_key_to_date()` → `set_period_date` callback in `ClaimsPeriod`

From Lambda handlers:
- `claims_get/handler.py` → `ClaimsController#show` and `#index`
- `claims_create/handler.py` → `ClaimsController#create`
- `claims_update/handler.py` → `ClaimsController#update`
- `claims_delete/handler.py` → `ClaimsController#destroy`

From `seed.sql`:
- Category reference data → `db/seeds/development.rb`
- January 2017 counts → seed data with actual COBOL OUTCLAIM.txt values

**Location on disk:** `/Users/ayannamuhammad/cobol-programming-course-main/aws-unemployment-claims-analysis/unemployment-claims-project/aws-modernization/`

---

## Part 3: Building the Rails Integration (Steps 9-17)

**Goal:** Bring the unemployment claims system into the Rails sandbox app with full UI screens. All of this happened AFTER reading the mainframe code (step 8) and BEFORE launching the app (step 18).

### Phase 1: Database Layer — Steps 9-10

Created 4 database tables to replace the COBOL VSAM file structure:

| Table | What it replaces | Key features |
|---|---|---|
| `demographic_categories` | COBOL 88-level hardcoded values | 42 categories across 5 types, unique index on category_code |
| `claims_periods` | VSAM record key (bytes 1-8) | Temporal versioning (effective_from/to), partial unique index for R09 duplicate detection |
| `claim_demographic_counts` | VSAM data fields (bytes 9-260) | Foreign keys to periods + categories, unique composite index |
| `claim_audit_logs` | Nothing (COBOL had no audit) | Immutable trail with before/after hashes, indexed for filtering |

**Commands used:**
```bash
docker compose run --rm ayannasandbox bin/rails generate migration CreateDemographicCategories
docker compose run --rm ayannasandbox bin/rails generate migration CreateClaimsPeriods
docker compose run --rm ayannasandbox bin/rails generate migration CreateClaimDemographicCounts
docker compose run --rm ayannasandbox bin/rails generate migration CreateClaimAuditLogs
docker compose run --rm ayannasandbox bin/rails db:migrate
```

### Phase 2: Models — Step 11

Created Rails models with business rule validations:

| Model | Business rules enforced |
|---|---|
| `DemographicCategory` | Validates category_type is one of 5 allowed types, unique category_code |
| `ClaimsPeriod` | R16 (valid MMDDYYYY format), R09 (no duplicates), R15 (cross-category totals) |
| `ClaimDemographicCount` | R17 (non-negative counts), R18 (realistic ceiling of 10M) |
| `ClaimAuditLog` | Required fields, `record!` class method for easy logging |

**Key concept:** Business rules that lived in scattered COBOL IF/ELSE blocks now live in model validations. Rails blocks invalid data automatically.

### Phase 3: Controllers + Policies — Steps 12-13

| Controller | Actions | What it replaces |
|---|---|---|
| `ClaimsController` | index, show, new, create, edit, update, destroy | 4 Python Lambda handlers + COBOL UNEMPCLM.cbl |
| `ClaimAuditLogsController` | index (read-only) | New capability (no COBOL equivalent) |
| `ClaimsReportsController` | show | COBOL OUTCLAIM.txt report + Python claims_report Lambda |

**Key features:**
- All write operations wrapped in database transactions
- Temporal versioning on update (old version preserved, new version created)
- Soft delete (marks inactive instead of destroying)
- Automatic audit logging on every create, update, delete
- Pundit authorization policies for access control

### Phase 4: Views — Step 14

| Screen | File | What it shows |
|---|---|---|
| Claims list | `app/views/claims/index.html.erb` | Table of all filing periods with R15 pass/fail status |
| Claim detail | `app/views/claims/show.html.erb` | Demographic breakdowns organized by category type |
| New claim form | `app/views/claims/new.html.erb` | Form with grouped inputs for all 42 categories |
| Edit claim form | `app/views/claims/edit.html.erb` | Pre-filled form with temporal versioning notice |
| Shared form partial | `app/views/claims/_form.html.erb` | Reusable form component (used by new + edit) |
| Audit trail | `app/views/claim_audit_logs/index.html.erb` | Filterable log of all operations |
| Report | `app/views/claims_reports/show.html.erb` | Summary dashboard with R15 validation status |

All screens use the U.S. Web Design System (USWDS) for government-standard styling.

### Phase 5: Wiring — Steps 15-17

| What | File changed | Details |
|---|---|---|
| Routes | `config/routes.rb` | Added `resources :claims`, audit logs, and report routes |
| Navigation | `app/views/application/_header.html.erb` | Added "Claims" link to the app nav bar |
| Seed data | `db/seeds/development.rb` | Loaded 42 categories + January 2017 claims from COBOL OUTCLAIM.txt |
| Policies | `app/policies/claims_period_policy.rb` | Pundit authorization (allows all actions for logged-in users) |

**Command to seed:**
```bash
docker compose run --rm ayannasandbox bin/rails db:seed
```

---

## Part 4: Launch and Verify (Step 18)

| Step | Command | Result |
|---|---|---|
| Start the app | `make start-container` | Rails app + PostgreSQL running in Docker |
| Visit the app | http://localhost:3100 | Home page with sign up / sign in |
| Sign up | Any email + password (mock auth) | Account created, redirected to dashboard |
| Navigate to Claims | Click "Claims" in nav bar | Claims index page with January 2017 data |
| View claim detail | Click "January 2017" | Demographic breakdowns with R15 validation status |

**Finding:** The R15 cross-category validation correctly flags the January 2017 seed data as FAIL because the original COBOL data has mismatched totals (age=37,353 vs race=34,723). This is data the COBOL system accepted silently — the new system catches it.

---

## Files Created

### Reference Documents
| File | Purpose |
|---|---|
| `rails-setup-guide.md` | Detailed Docker + Rails setup steps with explanations |
| `rails-claims-integration-guide.md` | Detailed 22-step integration guide with COBOL-to-Rails mapping |
| `project-journey-overview.md` | This file — high-level summary of the entire journey |

### Rails App Files (in `/Users/ayannamuhammad/ayannasandbox/`)
```
db/migrate/
  20260416220957_create_demographic_categories.rb
  20260416221050_create_claims_periods.rb
  20260416221122_create_claim_demographic_counts.rb
  20260416221147_create_claim_audit_logs.rb

app/models/
  demographic_category.rb
  claims_period.rb
  claim_demographic_count.rb
  claim_audit_log.rb

app/controllers/
  claims_controller.rb
  claim_audit_logs_controller.rb
  claims_reports_controller.rb

app/policies/
  claims_period_policy.rb
  claim_audit_log_policy.rb

app/views/claims/
  index.html.erb
  show.html.erb
  new.html.erb
  edit.html.erb
  _form.html.erb

app/views/claim_audit_logs/
  index.html.erb

app/views/claims_reports/
  show.html.erb

db/seeds/
  development.rb

config/routes.rb          (modified)
app/views/application/_header.html.erb  (modified)
```

---

## COBOL to Rails: What Changed

| COBOL | Rails |
|---|---|
| VSAM KSDS file | PostgreSQL tables with foreign keys and indexes |
| 88-level hardcoded values | `demographic_categories` database table |
| REWRITE (destructive updates) | Temporal versioning (old versions preserved) |
| No audit trail | `claim_audit_logs` with SHA-256 hashes |
| 12 business rules (R01-R12) | 18 business rules (R01-R20) |
| Batch commands via SYSIN | Web UI with forms and buttons |
| OUTCLAIM.txt text report | Interactive report dashboard |
| 200-command batch limit | No limit |
| PIC X(05) overflows at 99,999 | INTEGER supports 2,147,483,647 |
| Manual text output review | Real-time R15 pass/fail validation in UI |
