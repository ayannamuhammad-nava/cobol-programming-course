# Local Demo Setup - Step-by-Step Instructions

This guide walks you through running the modernized AWS Unemployment Claims
system locally using Docker and PostgreSQL. No AWS account required.

---

## Prerequisites

Before starting, make sure you have these installed on your machine:

- **Docker Desktop** - runs the PostgreSQL database in a container
- **Python 3.11+** - runs the Lambda handler code locally
- **pip** - installs the Python dependencies

---

## Step 1: Start the PostgreSQL Database Container

**What this does:** Launches a PostgreSQL 15 database inside a Docker container
on your machine. This replaces the AWS Aurora PostgreSQL database that the
production system would use. The container is preconfigured with a database
named `unemployment_claims` and a user `claims_admin`.

```bash
cd aws-modernization/demo
docker compose up -d
```

**How to verify:** Run `docker ps` and confirm you see a container named
`claims-demo-db` with status "Up" and port `5432` mapped.

---

## Step 2: Install Python Dependencies

**What this does:** Installs the two Python packages that the Lambda handlers
need: `psycopg2-binary` (PostgreSQL database driver) and `boto3` (AWS SDK,
used by the report handler but not needed for the core CRUD demo).

```bash
pip install psycopg2-binary boto3
```

---

## Step 3: Create the Database Schema

**What this does:** Runs the SQL schema file against your local PostgreSQL to
create the four core tables that replace the legacy COBOL VSAM file:

| Table | Purpose | What it replaces in COBOL |
|-------|---------|--------------------------|
| `claims_period` | Master record for each filing period | VSAM record key (bytes 1-8) |
| `claim_demographic_counts` | Demographic counts per period | VSAM bytes 9-260 (43 comma-delimited fields) |
| `demographic_category_ref` | Reference data for categories | Hardcoded COBOL 88-level values |
| `claim_audit_log` | Immutable audit trail | Nothing (COBOL had no audit capability) |

It also creates a validation view (`v_cross_category_totals`) that checks
whether age, race, and gender totals match for each period.

```bash
PGPASSWORD=demo_password psql -h localhost -U claims_admin -d unemployment_claims -f ../data/schema.sql
```

---

## Step 4: Load the Seed Data

**What this does:** Inserts the January 2017 unemployment claims record from
the original COBOL output file (`OUTCLAIM.txt`) into the new database. This
includes:

- **42 reference categories** across 5 demographic types (age, ethnicity,
  industry, race, gender)
- **1 filing period** (January 2017) with all demographic count breakdowns
- **1 audit log entry** recording the initial data migration

This is the same data that the original COBOL program (`UNEMPCLM.cbl`)
processed and wrote to `OUTCLAIM.txt`.

```bash
PGPASSWORD=demo_password psql -h localhost -U claims_admin -d unemployment_claims -f ../data/seed.sql
```

---

## Step 5: Run the Demo Script

**What this does:** Executes a Python script that calls each Lambda handler
function directly (without going through API Gateway). The script simulates
the API Gateway events that each handler expects and walks through a complete
CRUD lifecycle:

| Demo Step | Operation | COBOL Equivalent |
|-----------|-----------|-----------------|
| 1 | **READ** seed data | `READ CLAIMS-FILE KEY IS '01012017'` |
| 2 | **CREATE** new claim (Feb 2017) | `GETCLAIM Insert (I)` |
| 3 | **READ** back the created claim | Verification read |
| 4 | **UPDATE** with revised numbers | `GETCLAIM Update (U)` with temporal versioning |
| 5 | **READ** updated record | Verification read |
| 6 | **RANGE QUERY** all periods | `START` + `READ NEXT` sequential scan |
| 7 | **DELETE** (soft delete) | `GETCLAIM Delete (D)` with data preservation |
| 8 | **READ** deleted record (404) | Confirms deletion |
| 9 | **AUDIT TRAIL** review | New capability not in COBOL |

The script also validates business rules during creation:
- **R07/R08**: Read-back confirmation after write
- **R09**: Duplicate record detection
- **R12**: Audit logging for every write operation
- **R15**: Cross-category totals must match (age = race = gender)
- **R16**: Valid MMDDYYYY period key format
- **R17**: Non-negative claim counts
- **R18**: Realistic count ceiling

```bash
cd aws-modernization/demo
python demo.py
```

---

## Step 6: (Optional) Explore the Database Directly

**What this does:** Opens an interactive PostgreSQL shell where you can run
SQL queries against the data. Some useful queries:

```bash
PGPASSWORD=demo_password psql -h localhost -U claims_admin -d unemployment_claims
```

Once inside the `psql` shell:

```sql
-- See all current filing periods
SELECT period_key, period_date, region_code, is_current, effective_from
FROM claims_period
ORDER BY period_key;

-- See demographic counts for January 2017
SELECT cdc.category_type, cdc.category_code, cdc.count
FROM claim_demographic_counts cdc
JOIN claims_period cp ON cp.id = cdc.period_id
WHERE cp.period_key = '01012017' AND cp.is_current = TRUE
ORDER BY cdc.category_type, cdc.category_code;

-- Check cross-category totals (R15 validation)
SELECT * FROM v_cross_category_totals;

-- View the full audit trail
SELECT operation, period_key, user_id, timestamp_utc
FROM claim_audit_log
ORDER BY timestamp_utc;
```

---

## Step 7: Tear Down

**What this does:** Stops and removes the Docker container and its data volume.
This completely cleans up everything created during the demo.

```bash
cd aws-modernization/demo
docker compose down -v
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `docker compose up` fails | Make sure Docker Desktop is running |
| `psql: command not found` | Install PostgreSQL client: `brew install libpq` then `brew link --force libpq` |
| Port 5432 already in use | Stop any existing PostgreSQL: `brew services stop postgresql` or change the port in `docker-compose.yml` |
| `ModuleNotFoundError: psycopg2` | Run `pip install psycopg2-binary` |
| Connection refused | Wait a few seconds after `docker compose up` for Postgres to initialize |
