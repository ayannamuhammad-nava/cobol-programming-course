-- =============================================================================
-- Seed data from OUTCLAIM.txt - January 2017 filing period (final updated state)
-- This represents the record after DELETE, INSERT, and UPDATE operations
-- as documented in the modernization report.
-- =============================================================================

-- Insert reference categories first
INSERT INTO demographic_category_ref (category_code, category_type, display_name, display_order) VALUES
-- Age categories (8 brackets + INA)
('age_ina',          'age', 'Not Applicable',           0),
('age_under_22',     'age', 'Under 22',                 1),
('age_22_24',        'age', '22-24',                    2),
('age_25_34',        'age', '25-34',                    3),
('age_35_44',        'age', '35-44',                    4),
('age_45_54',        'age', '45-54',                    5),
('age_55_59',        'age', '55-59',                    6),
('age_60_64',        'age', '60-64',                    7),
('age_65_over',      'age', '65 and Over',              8),
-- Ethnicity categories
('eth_ina',                  'ethnicity', 'Not Applicable',           0),
('eth_hispanic_latino',      'ethnicity', 'Hispanic or Latino',       1),
('eth_not_hispanic_latino',  'ethnicity', 'Not Hispanic or Latino',   2),
-- Industry categories (20 sectors)
('ind_ina',               'industry', 'Not Applicable',                              0),
('ind_wholesale_trade',   'industry', 'Wholesale Trade',                             1),
('ind_transportation',    'industry', 'Transportation & Warehousing',                2),
('ind_construction',      'industry', 'Construction',                                3),
('ind_finance_insurance', 'industry', 'Finance & Insurance',                         4),
('ind_manufacturing',     'industry', 'Manufacturing',                               5),
('ind_agriculture',       'industry', 'Agriculture/Forestry/Fishing/Hunting',        6),
('ind_public_admin',      'industry', 'Public Administration',                       7),
('ind_utilities',         'industry', 'Utilities',                                   8),
('ind_accommodation_food','industry', 'Accommodation & Food Services',               9),
('ind_information',       'industry', 'Information',                                10),
('ind_professional_tech', 'industry', 'Professional/Scientific/Tech Services',      11),
('ind_real_estate',       'industry', 'Real Estate & Rental & Leasing',             12),
('ind_other_services',    'industry', 'Other Services (excl. Public Admin)',         13),
('ind_management',        'industry', 'Management of Companies & Enterprises',      14),
('ind_educational',       'industry', 'Educational Services',                       15),
('ind_mining',            'industry', 'Mining',                                     16),
('ind_health_care',       'industry', 'Health Care & Social Assistance',            17),
('ind_arts_entertainment','industry', 'Arts, Entertainment & Recreation',            18),
('ind_admin_support',     'industry', 'Admin & Support / Waste Mgmt',               19),
('ind_retail_trade',      'industry', 'Retail Trade',                               20),
-- Race categories
('race_ina',              'race', 'Not Applicable',                                  0),
('race_white',            'race', 'White',                                           1),
('race_asian',            'race', 'Asian',                                           2),
('race_black',            'race', 'Black or African American',                       3),
('race_native_american',  'race', 'American Indian or Alaskan Native',               4),
('race_pacific_islander', 'race', 'Native Hawaiian or Other Pacific Islander',       5),
-- Gender categories
('gender_ina',    'gender', 'Not Applicable', 0),
('gender_female', 'gender', 'Female',         1),
('gender_male',   'gender', 'Male',           2);

-- Insert the January 2017 filing period (from OUTCLAIM.txt final state)
INSERT INTO claims_period (id, period_key, period_date, is_current, effective_from)
VALUES ('a1b2c3d4-e5f6-7890-abcd-ef1234567890', '01012017', '2017-01-01', TRUE, NOW());

-- Insert demographic counts (values from the modernization report sample record)
INSERT INTO claim_demographic_counts (period_id, category_type, category_code, count) VALUES
-- Age (updated values from OUTCLAIM.txt)
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_ina',       0),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_under_22',  400),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_22_24',     1000),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_25_34',     8000),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_35_44',     8412),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_45_54',     8700),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_55_59',     4500),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_60_64',     3500),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'age', 'age_65_over',   2841),
-- Ethnicity
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'ethnicity', 'eth_ina',                  0),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'ethnicity', 'eth_hispanic_latino',       1676),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'ethnicity', 'eth_not_hispanic_latino',   30172),
-- Race
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'race', 'race_ina',              0),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'race', 'race_white',            26362),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'race', 'race_asian',            1200),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'race', 'race_black',            6461),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'race', 'race_native_american',  500),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'race', 'race_pacific_islander', 200),
-- Gender
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'gender', 'gender_ina',    0),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'gender', 'gender_female', 14186),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'gender', 'gender_male',   23167),
-- Industry (selected values from report; others set to estimates)
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_ina',               0),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_wholesale_trade',    800),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_transportation',     1200),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_construction',       8000),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_finance_insurance',  600),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_manufacturing',      3500),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_agriculture',        200),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_public_admin',       400),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_utilities',          150),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_accommodation_food', 4000),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_information',        700),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_professional_tech',  1800),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_real_estate',        500),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_other_services',     1500),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_management',         300),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_educational',        900),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_mining',             100),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_health_care',        4200),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_arts_entertainment', 800),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_admin_support',      3500),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'industry', 'ind_retail_trade',       4200);

-- Insert a seed audit log entry
INSERT INTO claim_audit_log (user_id, operation, period_key, timestamp_utc, after_hash)
VALUES ('migration-script', 'INSERT', '01012017', NOW(),
        'seed-data-from-outclaim-txt');
