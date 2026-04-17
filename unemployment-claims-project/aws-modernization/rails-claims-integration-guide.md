# Integrating the Unemployment Claims System into Rails

This guide walks through every step to bring the modernized COBOL unemployment claims system into the Rails sandbox app. Each phase builds on the previous one.

---

## Phase 1: Database Layer (Steps 1-4)

**What you're learning:** How Rails manages database tables through migrations instead of writing raw SQL.

In COBOL, data lived in a VSAM file with fixed-length records. In Rails, data lives in PostgreSQL tables that you create using migration files. Migrations are Ruby scripts that describe changes to your database — Rails tracks which ones have run so your database stays in sync across all developers.

Each migration runs inside the Docker container:
```bash
docker compose run --rm ayannasandbox bin/rails generate migration <MigrationName>
```

After generating, you edit the migration file in `db/migrate/`, then apply it:
```bash
docker compose run --rm ayannasandbox bin/rails db:migrate
```

### Step 1: Create `demographic_categories` table

**Command:**
```bash
docker compose run --rm ayannasandbox bin/rails generate migration CreateDemographicCategories
```

**What it does:** Creates the reference table for all 42 demographic categories across 5 types (age, ethnicity, industry, race, gender).

**Why it matters:** In COBOL, these categories were hardcoded as 88-level values in the program source. If you needed to add a new race category (like OMB SPD-15 requires), you had to rewrite and recompile the COBOL program. In Rails, they live in a database table — you just insert a new row.

**What the COBOL looked like:**
```cobol
88 AGE-UNDER-22    VALUE 'age_under_22'.
88 AGE-22-24       VALUE 'age_22_24'.
```

**What the Rails migration creates:**

| Column | Type | Purpose |
|---|---|---|
| `id` | uuid | Unique identifier |
| `category_type` | string | One of: age, ethnicity, industry, race, gender |
| `category_code` | string | e.g., "age_under_22", "race_white" |
| `display_name` | string | Human-readable label, e.g., "Under 22" |
| `sort_order` | integer | Controls display ordering |

---

### Step 2: Create `claims_periods` table

**Command:**
```bash
docker compose run --rm ayannasandbox bin/rails generate migration CreateClaimsPeriods
```

**What it does:** Creates the master record table for filing periods. Each row represents one month of unemployment claims data for a region.

**Why it matters:** This replaces the VSAM record key (bytes 1-8 of each record). The COBOL program identified records by an 8-character key like "01012017" (January 1, 2017). Rails uses the same concept but adds temporal versioning — when you update a record, the old version is preserved instead of being destroyed by VSAM REWRITE.

**What the Rails migration creates:**

| Column | Type | Purpose |
|---|---|---|
| `id` | uuid | Unique identifier |
| `period_key` | string | MMDDYYYY format, e.g., "01012017" (matches COBOL key) |
| `period_date` | date | Actual date value for easier querying |
| `region_code` | string | Region identifier, e.g., "US-CA" |
| `is_current` | boolean | Whether this is the active version (temporal versioning) |
| `effective_from` | datetime | When this version became active |
| `effective_to` | datetime | When this version was superseded (null if current) |

---

### Step 3: Create `claim_demographic_counts` table

**Command:**
```bash
docker compose run --rm ayannasandbox bin/rails generate migration CreateClaimDemographicCounts
```

**What it does:** Creates the table that stores the actual count numbers — how many unemployment claims were filed by each demographic group in a given period.

**Why it matters:** In COBOL, all 43 count fields were packed into bytes 9-260 of a single VSAM record as comma-delimited text. If a count exceeded 99,999 (PIC X(05)), it overflowed. In Rails, each count is its own row with a proper integer column that supports values up to 2,147,483,647.

**What the COBOL looked like:**
```
Record: "01012017,1234,5678,9012,..." (43 fields crammed into one line)
```

**What the Rails migration creates:**

| Column | Type | Purpose |
|---|---|---|
| `id` | uuid | Unique identifier |
| `period_id` | uuid (FK) | Links to `claims_periods` table |
| `demographic_category_id` | uuid (FK) | Links to `demographic_categories` table |
| `count` | integer | The actual claim count (replaces PIC X(05)) |

---

### Step 4: Create `claim_audit_logs` table

**Command:**
```bash
docker compose run --rm ayannasandbox bin/rails generate migration CreateClaimAuditLogs
```

**What it does:** Creates an immutable audit trail that records every create, update, and delete operation.

**Why it matters:** The original COBOL system had NO audit capability. If someone changed a record, the old data was gone forever (VSAM REWRITE). This table records who did what, when, and stores hashes of the data before and after the change. This is critical for government compliance and regulatory requirements.

**What the Rails migration creates:**

| Column | Type | Purpose |
|---|---|---|
| `id` | uuid | Unique identifier |
| `operation` | string | One of: CREATE, UPDATE, DELETE |
| `period_key` | string | Which period was affected |
| `user_id` | string | Who performed the operation |
| `timestamp_utc` | datetime | When it happened |
| `before_hash` | string | SHA-256 hash of data before the change |
| `after_hash` | string | SHA-256 hash of data after the change |
| `details` | jsonb | Additional context about the change |

---

## Phase 2: Models (Steps 5-9)

**What you're learning:** How Rails models define relationships between tables and enforce business rules.

In COBOL, validation logic was scattered across `UNEMPCLM.cbl` and `GETCLAIM.cbl` in IF/ELSE blocks. In Rails, validations live in model files — one file per table. When someone tries to save invalid data, Rails blocks it automatically.

Model files live in `app/models/` and are created manually (no generator needed).

### Step 5: Create `DemographicCategory` model

**File:** `app/models/demographic_category.rb`

**What it does:** Tells Rails how to read and write the `demographic_categories` table. Defines the relationship: one category has many counts.

**Key features:**
- Scopes for filtering by type (e.g., `DemographicCategory.age` returns all age categories)
- Validates that `category_type` is one of the 5 allowed types
- Validates uniqueness of `category_code`

---

### Step 6: Create `ClaimsPeriod` model

**File:** `app/models/claims_period.rb`

**What it does:** Defines the main claims record with validations and relationships.

**Business rules enforced:**
- **R16** — `period_key` must be valid MMDDYYYY format with day=01
- **R09** — No duplicate period_key for current records (duplicate detection)
- Has many `claim_demographic_counts` (one-to-many relationship)
- Has many `claim_audit_logs`
- Supports temporal versioning (creates new version on update instead of overwriting)

---

### Step 7: Create `ClaimDemographicCount` model

**File:** `app/models/claim_demographic_count.rb`

**What it does:** Defines each demographic count entry with validations.

**Business rules enforced:**
- **R17** — Count must be a non-negative integer (>= 0)
- **R18** — Count must be below a realistic ceiling (configurable threshold, prevents data entry errors)
- Belongs to a `claims_period` and a `demographic_category`

---

### Step 8: Create `ClaimAuditLog` model

**File:** `app/models/claim_audit_log.rb`

**What it does:** Defines the audit record. This model is append-only — records are created but never updated or deleted.

**Key features:**
- Automatically sets `timestamp_utc` on creation
- Computes `before_hash` and `after_hash` using SHA-256
- Belongs to a `claims_period` (optional, for delete operations the period may no longer exist)

---

### Step 9: Add cross-category validation (R15)

**File:** Updated in `app/models/claims_period.rb`

**What it does:** Adds a custom validation that checks: the sum of all age counts = sum of all race counts = sum of all gender counts for a given period.

**Why it matters:** This is the most important business rule from the original COBOL system. If these totals don't match, the data is inconsistent. The original COBOL program checked this but only had 12 rules. The modernized system adds 6 new rules (R15-R20), and R15 is the cross-category validation.

**Example:**
```
Age total:    200 + 500 + 1200 + 1000 + 800 + 500 + 400 + 400 = 5000
Race total:   3000 + 500 + 1000 + 300 + 200 = 5000
Gender total: 2400 + 2600 = 5000
All match = VALID
```

---

## Phase 3: Controllers (Steps 10-12)

**What you're learning:** How Rails handles HTTP requests and connects the UI to the database.

In the Python/Lambda version, each operation was a separate Lambda function. In Rails, related operations are grouped into a single controller. Each method in the controller is called an "action."

Controller files live in `app/controllers/`.

### Step 10: Create `ClaimsController`

**File:** `app/controllers/claims_controller.rb`

**What it does:** Handles all CRUD operations for claims. This single controller replaces 4 separate Python Lambda handlers.

| Action | HTTP Method | URL | Python Lambda it replaces |
|---|---|---|---|
| `index` | GET | `/claims` | `claims_get` (range mode) |
| `show` | GET | `/claims/:id` | `claims_get` (by key) |
| `new` | GET | `/claims/new` | No equivalent (Lambda had no UI) |
| `create` | POST | `/claims` | `claims_create` |
| `edit` | GET | `/claims/:id/edit` | No equivalent (Lambda had no UI) |
| `update` | PATCH | `/claims/:id` | `claims_update` |
| `destroy` | DELETE | `/claims/:id` | `claims_delete` |

**Key features:**
- `new` and `edit` are UI-only actions — they show forms. Lambdas didn't need these because they were API-only.
- `create` and `update` trigger model validations (R09, R15-R18) automatically
- `destroy` performs a soft delete (marks `is_current = false` instead of removing the row)
- Every write operation creates an audit log entry

---

### Step 11: Create `ClaimAuditLogsController`

**File:** `app/controllers/claim_audit_logs_controller.rb`

**What it does:** Provides a read-only view of the audit trail. Only has an `index` action.

| Action | HTTP Method | URL | What it shows |
|---|---|---|---|
| `index` | GET | `/claim-audit-logs` | All audit entries, newest first, with filters |

---

### Step 12: Create `ClaimsReportsController`

**File:** `app/controllers/claims_reports_controller.rb`

**What it does:** Generates summary statistics and cross-category reports. Replaces the COBOL report that wrote to `OUTCLAIM.txt` and the Python `claims_report` Lambda.

| Action | HTTP Method | URL | What it shows |
|---|---|---|---|
| `show` | GET | `/claims-report` | Summary stats, cross-category totals, trend data |

---

## Phase 4: Views & UI (Steps 13-19)

**What you're learning:** How Rails renders HTML pages using templates and the USWDS design system.

Views are HTML files with embedded Ruby (`.html.erb`). Rails automatically connects them to controller actions by naming convention: `ClaimsController#index` renders `app/views/claims/index.html.erb`.

The sandbox app already includes USWDS (U.S. Web Design System), so all our pages will use government-standard components like tables, forms, alerts, and buttons.

### Step 13: Claims index page

**File:** `app/views/claims/index.html.erb`

**What you'll see:** A USWDS-styled table showing all filing periods with columns for period date, region, status (active/deleted), and action links (View, Edit, Delete). Includes a "New Claim" button at the top.

---

### Step 14: Claim detail page

**File:** `app/views/claims/show.html.erb`

**What you'll see:** A detail view for a single filing period. Demographic counts are organized into collapsible sections by category type (Age, Race, Gender, Ethnicity, Industry). Shows the cross-category totals validation status (R15 pass/fail).

---

### Step 15: New claim form

**File:** `app/views/claims/new.html.erb`

**What you'll see:** A form to create a new filing period. Uses the shared form partial (Step 17).

---

### Step 16: Edit claim form

**File:** `app/views/claims/edit.html.erb`

**What you'll see:** Same form as "new" but pre-filled with existing data. When submitted, Rails creates a new temporal version instead of overwriting the old one.

---

### Step 17: Shared form partial

**File:** `app/views/claims/_form.html.erb`

**What it does:** A reusable form component shared between the New and Edit pages. Contains:
- Period key input (MMDDYYYY)
- Region code dropdown
- Grouped number inputs for each demographic category (Age, Race, Gender, Ethnicity, Industry)
- Inline validation error messages
- Submit button

**What is a partial?** A partial is a reusable chunk of HTML. The underscore prefix (`_form`) tells Rails it's a partial. Both `new.html.erb` and `edit.html.erb` include it with `<%= render 'form' %>` so you don't duplicate the form code.

---

### Step 18: Audit trail page

**File:** `app/views/claim_audit_logs/index.html.erb`

**What you'll see:** A USWDS table showing every operation performed on claims data. Columns: Operation (CREATE/UPDATE/DELETE), Period Key, User, Timestamp, Before Hash, After Hash. This is the brand new capability that didn't exist in COBOL.

---

### Step 19: Report page

**File:** `app/views/claims_reports/show.html.erb`

**What you'll see:** A summary dashboard showing:
- Total number of filing periods
- Cross-category totals validation status for all periods
- Demographic breakdown charts/tables
- This replaces the COBOL `OUTCLAIM.txt` report

---

## Phase 5: Wiring It Together (Steps 20-22)

**What you're learning:** How Rails routes URLs to controllers and how to load initial data.

### Step 20: Add routes

**File:** `config/routes.rb`

**What it does:** Maps URLs to controller actions. Without routes, Rails doesn't know what to do when someone visits `/claims`.

**What gets added:**
```ruby
resources :claims
resources :claim_audit_logs, only: [:index]
resource :claims_report, only: [:show]
```

**What `resources :claims` expands to:**

| URL | HTTP Method | Controller Action |
|---|---|---|
| `/claims` | GET | `claims#index` |
| `/claims/new` | GET | `claims#new` |
| `/claims` | POST | `claims#create` |
| `/claims/:id` | GET | `claims#show` |
| `/claims/:id/edit` | GET | `claims#edit` |
| `/claims/:id` | PATCH | `claims#update` |
| `/claims/:id` | DELETE | `claims#destroy` |

One line of code creates 7 routes. That's the power of Rails conventions.

---

### Step 21: Add navigation link

**File:** Navigation partial in `app/views/layouts/`

**What it does:** Adds an "Unemployment Claims" link to the app's navigation bar so users can find the new feature. This is a small edit to the existing layout file.

---

### Step 22: Seed data

**File:** `db/seeds.rb`

**What it does:** Loads initial data into the database:
- **42 demographic categories** across 5 types (from the original COBOL 88-level definitions)
- **January 2017 claims record** (from the original COBOL output file `OUTCLAIM.txt`)
- **1 audit log entry** recording the data migration

**Command to run:**
```bash
docker compose run --rm ayannasandbox bin/rails db:seed
```

---

## Summary: COBOL to Rails Mapping

| COBOL Concept | Rails Equivalent |
|---|---|
| VSAM KSDS file | PostgreSQL tables |
| 88-level values | `demographic_categories` table |
| Record key (bytes 1-8) | `claims_periods.period_key` |
| Record data (bytes 9-260) | `claim_demographic_counts` rows |
| UNEMPCLM.cbl (orchestrator) | `ClaimsController` |
| GETCLAIM.cbl (data layer) | Rails models + validations |
| SYSIN commands (R/I/U/D) | HTTP methods (GET/POST/PATCH/DELETE) |
| OUTCLAIM.txt report | `ClaimsReportsController` + view |
| No audit trail | `claim_audit_logs` table |
| REWRITE (destructive) | Temporal versioning (non-destructive) |
| 200-command batch limit | No limit |
| PIC X(05) overflow at 99,999 | INTEGER supports 2,147,483,647 |

---

## How to Run Commands

All commands run inside the Docker container:

```bash
# Generate a migration
docker compose run --rm ayannasandbox bin/rails generate migration <Name>

# Run migrations
docker compose run --rm ayannasandbox bin/rails db:migrate

# Start the app
make start-container

# View the app
# Visit http://localhost:3100
```
