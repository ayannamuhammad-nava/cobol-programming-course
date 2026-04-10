"""
Creates the SQLite database and loads schema + seed data.
This is the SQLite equivalent of running schema.sql and seed.sql
against PostgreSQL.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claims_demo.db")


def setup():
    # Remove old database if it exists so we start fresh
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # ---- Schema (adapted from schema.sql for SQLite) ----

    conn.executescript("""
        CREATE TABLE claims_period (
            id              TEXT PRIMARY KEY,
            period_key      TEXT NOT NULL,
            period_date     TEXT NOT NULL,
            region_code     TEXT,
            is_current      INTEGER NOT NULL DEFAULT 1,
            effective_from  TEXT NOT NULL DEFAULT (datetime('now')),
            effective_to    TEXT
        );

        CREATE UNIQUE INDEX idx_unique_current_period
            ON claims_period (period_key, COALESCE(region_code, ''))
            WHERE is_current = 1;

        CREATE INDEX idx_period_current ON claims_period (period_key, is_current);
        CREATE INDEX idx_period_date ON claims_period (period_date);

        CREATE TABLE demographic_category_ref (
            category_code   TEXT PRIMARY KEY,
            category_type   TEXT NOT NULL,
            display_name    TEXT NOT NULL,
            display_order   INTEGER NOT NULL,
            naics_code      TEXT,
            effective_from  TEXT NOT NULL DEFAULT (date('now')),
            effective_to    TEXT
        );

        CREATE INDEX idx_category_type ON demographic_category_ref (category_type);

        CREATE TABLE claim_demographic_counts (
            id              TEXT PRIMARY KEY,
            period_id       TEXT NOT NULL REFERENCES claims_period(id),
            category_type   TEXT NOT NULL,
            category_code   TEXT NOT NULL,
            count           INTEGER NOT NULL CHECK (count >= 0) CHECK (count <= 10000000),
            UNIQUE (period_id, category_code)
        );

        CREATE INDEX idx_counts_period ON claim_demographic_counts (period_id);
        CREATE INDEX idx_counts_category ON claim_demographic_counts (category_type, category_code);

        CREATE TABLE claim_audit_log (
            id              TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL,
            operation       TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
            period_key      TEXT NOT NULL,
            timestamp_utc   TEXT NOT NULL DEFAULT (datetime('now')),
            before_hash     TEXT,
            after_hash      TEXT
        );

        CREATE INDEX idx_audit_period ON claim_audit_log (period_key, timestamp_utc);
        CREATE INDEX idx_audit_user ON claim_audit_log (user_id, timestamp_utc);
        CREATE INDEX idx_audit_timestamp ON claim_audit_log (timestamp_utc);

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
        WHERE cp.is_current = 1
        GROUP BY cp.period_key, cp.period_date;
    """)

    # ---- Seed data (from seed.sql) ----

    # Reference categories
    categories = [
        ('age_ina', 'age', 'Not Applicable', 0),
        ('age_under_22', 'age', 'Under 22', 1),
        ('age_22_24', 'age', '22-24', 2),
        ('age_25_34', 'age', '25-34', 3),
        ('age_35_44', 'age', '35-44', 4),
        ('age_45_54', 'age', '45-54', 5),
        ('age_55_59', 'age', '55-59', 6),
        ('age_60_64', 'age', '60-64', 7),
        ('age_65_over', 'age', '65 and Over', 8),
        ('eth_ina', 'ethnicity', 'Not Applicable', 0),
        ('eth_hispanic_latino', 'ethnicity', 'Hispanic or Latino', 1),
        ('eth_not_hispanic_latino', 'ethnicity', 'Not Hispanic or Latino', 2),
        ('ind_ina', 'industry', 'Not Applicable', 0),
        ('ind_wholesale_trade', 'industry', 'Wholesale Trade', 1),
        ('ind_transportation', 'industry', 'Transportation & Warehousing', 2),
        ('ind_construction', 'industry', 'Construction', 3),
        ('ind_finance_insurance', 'industry', 'Finance & Insurance', 4),
        ('ind_manufacturing', 'industry', 'Manufacturing', 5),
        ('ind_agriculture', 'industry', 'Agriculture/Forestry/Fishing/Hunting', 6),
        ('ind_public_admin', 'industry', 'Public Administration', 7),
        ('ind_utilities', 'industry', 'Utilities', 8),
        ('ind_accommodation_food', 'industry', 'Accommodation & Food Services', 9),
        ('ind_information', 'industry', 'Information', 10),
        ('ind_professional_tech', 'industry', 'Professional/Scientific/Tech Services', 11),
        ('ind_real_estate', 'industry', 'Real Estate & Rental & Leasing', 12),
        ('ind_other_services', 'industry', 'Other Services (excl. Public Admin)', 13),
        ('ind_management', 'industry', 'Management of Companies & Enterprises', 14),
        ('ind_educational', 'industry', 'Educational Services', 15),
        ('ind_mining', 'industry', 'Mining', 16),
        ('ind_health_care', 'industry', 'Health Care & Social Assistance', 17),
        ('ind_arts_entertainment', 'industry', 'Arts, Entertainment & Recreation', 18),
        ('ind_admin_support', 'industry', 'Admin & Support / Waste Mgmt', 19),
        ('ind_retail_trade', 'industry', 'Retail Trade', 20),
        ('race_ina', 'race', 'Not Applicable', 0),
        ('race_white', 'race', 'White', 1),
        ('race_asian', 'race', 'Asian', 2),
        ('race_black', 'race', 'Black or African American', 3),
        ('race_native_american', 'race', 'American Indian or Alaskan Native', 4),
        ('race_pacific_islander', 'race', 'Native Hawaiian or Other Pacific Islander', 5),
        ('gender_ina', 'gender', 'Not Applicable', 0),
        ('gender_female', 'gender', 'Female', 1),
        ('gender_male', 'gender', 'Male', 2),
    ]

    conn.executemany(
        "INSERT INTO demographic_category_ref (category_code, category_type, display_name, display_order) VALUES (?, ?, ?, ?)",
        categories,
    )

    # January 2017 filing period
    period_id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    conn.execute(
        "INSERT INTO claims_period (id, period_key, period_date, is_current, effective_from) VALUES (?, ?, ?, 1, datetime('now'))",
        (period_id, '01012017', '2017-01-01'),
    )

    # Demographic counts
    from uuid import uuid4
    counts = [
        ('age', 'age_ina', 0),
        ('age', 'age_under_22', 400),
        ('age', 'age_22_24', 1000),
        ('age', 'age_25_34', 8000),
        ('age', 'age_35_44', 8412),
        ('age', 'age_45_54', 8700),
        ('age', 'age_55_59', 4500),
        ('age', 'age_60_64', 3500),
        ('age', 'age_65_over', 2841),
        ('ethnicity', 'eth_ina', 0),
        ('ethnicity', 'eth_hispanic_latino', 1676),
        ('ethnicity', 'eth_not_hispanic_latino', 30172),
        ('race', 'race_ina', 0),
        ('race', 'race_white', 26362),
        ('race', 'race_asian', 1200),
        ('race', 'race_black', 6461),
        ('race', 'race_native_american', 500),
        ('race', 'race_pacific_islander', 200),
        ('gender', 'gender_ina', 0),
        ('gender', 'gender_female', 14186),
        ('gender', 'gender_male', 23167),
        ('industry', 'ind_ina', 0),
        ('industry', 'ind_wholesale_trade', 800),
        ('industry', 'ind_transportation', 1200),
        ('industry', 'ind_construction', 8000),
        ('industry', 'ind_finance_insurance', 600),
        ('industry', 'ind_manufacturing', 3500),
        ('industry', 'ind_agriculture', 200),
        ('industry', 'ind_public_admin', 400),
        ('industry', 'ind_utilities', 150),
        ('industry', 'ind_accommodation_food', 4000),
        ('industry', 'ind_information', 700),
        ('industry', 'ind_professional_tech', 1800),
        ('industry', 'ind_real_estate', 500),
        ('industry', 'ind_other_services', 1500),
        ('industry', 'ind_management', 300),
        ('industry', 'ind_educational', 900),
        ('industry', 'ind_mining', 100),
        ('industry', 'ind_health_care', 4200),
        ('industry', 'ind_arts_entertainment', 800),
        ('industry', 'ind_admin_support', 3500),
        ('industry', 'ind_retail_trade', 4200),
    ]

    conn.executemany(
        "INSERT INTO claim_demographic_counts (id, period_id, category_type, category_code, count) VALUES (?, ?, ?, ?, ?)",
        [(str(uuid4()), period_id, cat, code, cnt) for cat, code, cnt in counts],
    )

    # Seed audit entry
    conn.execute(
        "INSERT INTO claim_audit_log (id, user_id, operation, period_key, timestamp_utc, after_hash) VALUES (?, ?, 'INSERT', '01012017', datetime('now'), 'seed-data-from-outclaim-txt')",
        (str(uuid4()), 'migration-script'),
    )

    conn.commit()
    conn.close()
    print(f"  Database created: {DB_PATH}")
    print(f"  Tables: claims_period, claim_demographic_counts, demographic_category_ref, claim_audit_log")
    print(f"  Seed data: January 2017 filing period with 42 demographic counts loaded")


if __name__ == "__main__":
    setup()
