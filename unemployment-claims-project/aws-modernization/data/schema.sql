-- =============================================================================
-- Unemployment Claims System - Aurora PostgreSQL Schema
-- Replaces VSAM KSDS with normalized, temporal, extensible relational model
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. claims_period - Filing period master record
--    Replaces: VSAM record key (bytes 1-8) + metadata
--    Key change: Temporal versioning via is_current + effective_from/to
-- =============================================================================

CREATE TABLE claims_period (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    period_key      CHAR(8)     NOT NULL,  -- MMDDYYYY format (matches COBOL key)
    period_date     DATE        NOT NULL,  -- Decoded date for SQL queries
    region_code     VARCHAR(10),           -- New: geographic dimension (not in COBOL)
    is_current      BOOLEAN     NOT NULL DEFAULT TRUE,
    effective_from  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to    TIMESTAMPTZ,           -- NULL = current version

    -- R16: Period key must be valid MMDDYYYY with DD=01
    CONSTRAINT chk_period_key_format
        CHECK (period_key ~ '^(0[1-9]|1[0-2])01(19|20)[0-9]{2}$'),

    -- Only one current version per period_key + region
    CONSTRAINT uq_current_period
        UNIQUE (period_key, region_code, is_current)
        -- Note: partial unique index below is more precise
);

-- Partial unique index: only one is_current=TRUE per period_key+region
CREATE UNIQUE INDEX idx_unique_current_period
    ON claims_period (period_key, COALESCE(region_code, ''))
    WHERE is_current = TRUE;

-- Query performance: most queries filter on is_current
CREATE INDEX idx_period_current ON claims_period (period_key, is_current);
CREATE INDEX idx_period_date ON claims_period (period_date);

COMMENT ON TABLE claims_period IS
    'Master record for each filing period. Temporal: old versions preserved with '
    'effective_to set. Replaces VSAM KSDS record key.';

-- =============================================================================
-- 2. demographic_category_ref - Reference data for demographic categories
--    Replaces: Hardcoded COBOL 88-level values and column positions
--    Key change: New categories added as data inserts, not code changes
-- =============================================================================

CREATE TABLE demographic_category_ref (
    category_code   VARCHAR(40) PRIMARY KEY,
    category_type   VARCHAR(20) NOT NULL,  -- age, ethnicity, industry, race, gender
    display_name    VARCHAR(100) NOT NULL,
    display_order   INTEGER NOT NULL,
    naics_code      VARCHAR(10),           -- For industry categories
    effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to    DATE,                  -- NULL = currently active

    CONSTRAINT chk_category_type
        CHECK (category_type IN ('age', 'ethnicity', 'industry', 'race', 'gender'))
);

CREATE INDEX idx_category_type ON demographic_category_ref (category_type);

COMMENT ON TABLE demographic_category_ref IS
    'Extensible demographic category reference. Supports OMB SPD-15 (2024) '
    '7-race categories and NAICS code updates without code changes.';

-- =============================================================================
-- 3. claim_demographic_counts - Filing period counts by category
--    Replaces: VSAM bytes 9-260 (43 comma-delimited fields)
--    Key changes:
--      - INTEGER columns replace PIC X(05) (max 99,999 -> 2,147,483,647)
--      - Normalized: one row per category instead of 43 columns
-- =============================================================================

CREATE TABLE claim_demographic_counts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    period_id       UUID        NOT NULL REFERENCES claims_period(id),
    category_type   VARCHAR(20) NOT NULL,
    category_code   VARCHAR(40) NOT NULL,
    count           INTEGER     NOT NULL,

    -- R17: Non-negative counts
    CONSTRAINT chk_count_non_negative CHECK (count >= 0),

    -- R18: Realistic ceiling (10 million per category per period)
    CONSTRAINT chk_count_ceiling CHECK (count <= 10000000),

    -- One count per category per period version
    CONSTRAINT uq_period_category UNIQUE (period_id, category_code)
);

CREATE INDEX idx_counts_period ON claim_demographic_counts (period_id);
CREATE INDEX idx_counts_category ON claim_demographic_counts (category_type, category_code);

COMMENT ON TABLE claim_demographic_counts IS
    'Demographic claim counts per filing period. Normalized from COBOL fixed '
    'column positions. INTEGER replaces PIC X(05) to prevent field overflow.';

-- =============================================================================
-- 4. claim_audit_log - Immutable audit trail
--    Replaces: Nothing (COBOL had no audit capability)
--    Addresses: Risk #3 (FISMA compliance), Rule R12
-- =============================================================================

CREATE TABLE claim_audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         VARCHAR(128) NOT NULL,
    operation       VARCHAR(10)  NOT NULL,
    period_key      CHAR(8)      NOT NULL,
    timestamp_utc   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    before_hash     VARCHAR(64),  -- SHA-256 of pre-operation state
    after_hash      VARCHAR(64),  -- SHA-256 of post-operation state

    CONSTRAINT chk_operation CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE'))
);

-- Append-only: no UPDATE or DELETE allowed on this table
-- Enforced via PostgreSQL RLS or application-level policy

CREATE INDEX idx_audit_period ON claim_audit_log (period_key, timestamp_utc);
CREATE INDEX idx_audit_user ON claim_audit_log (user_id, timestamp_utc);
CREATE INDEX idx_audit_timestamp ON claim_audit_log (timestamp_utc);

COMMENT ON TABLE claim_audit_log IS
    'Immutable audit trail for every write operation. Records user_id, operation, '
    'timestamp, and before/after hashes. Addresses FISMA and Federal Records Act.';

-- =============================================================================
-- 5. Validation view: R15 cross-category totals check
--    Runs nightly via EventBridge -> Lambda to detect data integrity issues
-- =============================================================================

CREATE VIEW v_cross_category_totals AS
SELECT
    cp.period_key,
    cp.period_date,
    SUM(CASE WHEN cdc.category_type = 'age' THEN cdc.count ELSE 0 END) AS age_total,
    SUM(CASE WHEN cdc.category_type = 'ethnicity' THEN cdc.count ELSE 0 END) AS ethnicity_total,
    SUM(CASE WHEN cdc.category_type = 'race' THEN cdc.count ELSE 0 END) AS race_total,
    SUM(CASE WHEN cdc.category_type = 'gender' THEN cdc.count ELSE 0 END) AS gender_total
FROM claims_period cp
JOIN claim_demographic_counts cdc ON cdc.period_id = cp.id
WHERE cp.is_current = TRUE
GROUP BY cp.period_key, cp.period_date;

COMMENT ON VIEW v_cross_category_totals IS
    'R15 validation: age_total = race_total = gender_total for each period. '
    'Rows where these differ indicate data integrity violations.';

-- Query to find violations:
-- SELECT * FROM v_cross_category_totals
-- WHERE age_total != race_total OR age_total != gender_total;
