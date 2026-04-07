# VSAM to Aurora PostgreSQL Migration Approach

## Overview

This document details the data migration from the IBM z/OS VSAM KSDS file to Amazon Aurora PostgreSQL. The migration is the highest-priority component (Phase A, Weeks 1-9) because the VSAM format is completely unportable to any cloud platform.

---

## Source: VSAM CLAIMS File

| Property | Value |
|----------|-------|
| File type | VSAM KSDS (Key-Sequenced Data Set) |
| Platform | IBM z/OS (not portable) |
| Record length | Variable, 1-260 bytes |
| Key | 8 bytes (MMDDYYYY, DD always 01) |
| Data payload | 252 bytes, 43 comma-delimited fields |
| Historical range | 2012-2021 (~120 monthly records) |
| Access mode | DYNAMIC (keyed + sequential) |

## Target: Aurora PostgreSQL

| Property | Value |
|----------|-------|
| Engine | Aurora PostgreSQL 15.4 |
| Tables | 4 (claims_period, claim_demographic_counts, demographic_category_ref, claim_audit_log) |
| Record key | UUID primary key + period_key CHAR(8) |
| Count fields | INTEGER (max 2,147,483,647 vs COBOL max 99,999) |
| Temporal | effective_from/effective_to on claims_period |
| Encryption | KMS at rest, TLS 1.3 in transit |

---

## Migration Steps

### Step 1: VSAM Export (Mainframe Side)

Extract all VSAM records to a flat file using a COBOL utility or IDCAMS REPRO:

```jcl
//EXPORT   EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//INFILE   DD DSN=CLAIMS,DISP=SHR
//OUTFILE  DD DSN=CLAIMS.EXPORT.CSV,
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(5,5)),
//            DCB=(RECFM=VB,LRECL=264,BLKSIZE=27998)
//SYSIN    DD *
  REPRO INFILE(INFILE) OUTFILE(OUTFILE)
/*
```

The output is a sequential file where each record is the raw VSAM content: 8-byte key followed by 252 bytes of comma-delimited data.

### Step 2: Transfer to S3

Upload the exported flat file to an S3 staging bucket:

```bash
# From a z/OS file transfer tool or AWS Transfer Family SFTP endpoint
aws s3 cp CLAIMS.EXPORT.CSV s3://claims-migration-staging/vsam-export/claims_raw.csv
```

### Step 3: Parse and Transform (AWS Glue or Python Script)

Convert the VSAM export into normalized Aurora-ready format:

```python
"""
VSAM-to-Aurora transformation script.
Runs as an AWS Glue job or standalone Python script.
"""

import csv
import uuid
from datetime import datetime

# Field mapping: positional index -> (category_type, category_code)
FIELD_MAP = [
    ("metadata", "date_time"),          # Field 1: ISO timestamp
    ("age", "age_ina"),                 # Field 2
    ("age", "age_under_22"),            # Field 3
    ("age", "age_22_24"),               # Field 4
    ("age", "age_25_34"),               # Field 5
    ("age", "age_35_44"),               # Field 6
    ("age", "age_45_54"),               # Field 7
    ("age", "age_55_59"),               # Field 8
    ("age", "age_60_64"),               # Field 9
    ("age", "age_65_over"),             # Field 10
    ("ethnicity", "eth_ina"),           # Field 11
    ("ethnicity", "eth_hispanic_latino"),       # Field 12
    ("ethnicity", "eth_not_hispanic_latino"),   # Field 13
    ("industry", "ind_ina"),            # Field 14
    ("industry", "ind_wholesale_trade"),        # Field 15
    ("industry", "ind_transportation"),         # Field 16
    ("industry", "ind_construction"),           # Field 17
    ("industry", "ind_finance_insurance"),      # Field 18
    ("industry", "ind_manufacturing"),          # Field 19
    ("industry", "ind_agriculture"),            # Field 20
    ("industry", "ind_public_admin"),           # Field 21
    ("industry", "ind_utilities"),              # Field 22
    ("industry", "ind_accommodation_food"),     # Field 23
    ("industry", "ind_information"),            # Field 24
    ("industry", "ind_professional_tech"),      # Field 25
    ("industry", "ind_real_estate"),            # Field 26
    ("industry", "ind_other_services"),         # Field 27
    ("industry", "ind_management"),             # Field 28
    ("industry", "ind_educational"),            # Field 29
    ("industry", "ind_mining"),                 # Field 30
    ("industry", "ind_health_care"),            # Field 31
    ("industry", "ind_arts_entertainment"),     # Field 32
    ("industry", "ind_admin_support"),          # Field 33
    ("industry", "ind_retail_trade"),           # Field 34
    ("race", "race_ina"),               # Field 35
    ("race", "race_white"),             # Field 36
    ("race", "race_asian"),             # Field 37
    ("race", "race_black"),             # Field 38
    ("race", "race_native_american"),   # Field 39
    ("race", "race_pacific_islander"),  # Field 40
    ("gender", "gender_ina"),           # Field 41
    ("gender", "gender_female"),        # Field 42
    ("gender", "gender_male"),          # Field 43
]


def parse_vsam_record(line: str) -> dict:
    """Parse a single VSAM export line into period + counts."""
    period_key = line[:8].strip()
    data_payload = line[8:].strip()
    fields = data_payload.split(",")

    month = int(period_key[0:2])
    year = int(period_key[4:8])
    period_date = f"{year}-{month:02d}-01"

    period_id = str(uuid.uuid4())

    counts = []
    for i, (cat_type, cat_code) in enumerate(FIELD_MAP):
        if cat_type == "metadata":
            continue
        value = int(fields[i].strip()) if i < len(fields) and fields[i].strip() else 0
        counts.append({
            "period_id": period_id,
            "category_type": cat_type,
            "category_code": cat_code,
            "count": value,
        })

    return {
        "period": {
            "id": period_id,
            "period_key": period_key,
            "period_date": period_date,
            "is_current": True,
            "effective_from": datetime.utcnow().isoformat(),
        },
        "counts": counts,
    }
```

### Step 4: Load into Aurora

```bash
# Generate SQL INSERT statements from transformed data
python transform_vsam.py > data/migrated_data.sql

# Load into Aurora
psql -h <aurora-endpoint> -U claims_admin -d unemployment_claims \
    -f data/schema.sql \
    -f data/migrated_data.sql
```

### Step 5: Reconciliation

Run field-level reconciliation between VSAM source and Aurora target:

```sql
-- Count total records
SELECT COUNT(DISTINCT period_key) AS aurora_period_count
FROM claims_period WHERE is_current = TRUE;

-- Compare with VSAM record count (should match exactly)

-- Verify cross-category totals (R15 check on migrated data)
SELECT period_key, age_total, race_total, gender_total
FROM v_cross_category_totals
WHERE age_total != race_total OR age_total != gender_total;

-- Spot-check specific records against VSAM source
SELECT cp.period_key, cdc.category_code, cdc.count
FROM claims_period cp
JOIN claim_demographic_counts cdc ON cdc.period_id = cp.id
WHERE cp.period_key = '01012017' AND cp.is_current = TRUE
ORDER BY cdc.category_code;
```

---

## Go/No-Go Criteria (Phase 2 Gate)

The migration is complete when:

1. **Record count match**: Aurora `claims_period` count equals VSAM record count
2. **Field-level match**: Every count field in every record matches between VSAM and Aurora
3. **14-day sync stability**: Nightly sync produces zero discrepancies for 14 consecutive days
4. **R15 baseline**: Cross-category totals check identifies all pre-existing mismatches (these are documented, not fixed during migration)
5. **Performance**: Single-key lookup < 10ms, range query (200 records) < 100ms

---

## Rollback Plan

If migration verification fails:

1. Aurora data is dropped and re-created from the VSAM export
2. VSAM remains the system of record until re-migration succeeds
3. The mainframe continues processing during the entire migration period
4. No data is deleted from VSAM until 90 days after production cutover
