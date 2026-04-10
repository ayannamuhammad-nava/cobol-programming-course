#!/usr/bin/env python3
"""
Local demo script for the AWS Unemployment Claims system.
Exercises all four CRUD operations (Create, Read, Update, Delete) against
a local SQLite database, simulating the API Gateway events that would
normally be sent to each Lambda function.

Requirements: Python 3.9+ (no pip installs needed -- uses only stdlib + project code)

Usage:
    python demo.py
"""

import json
import os
import sys
import textwrap
import types

# ---------------------------------------------------------------------------
# Step A: Set up the database (SQLite, created fresh each run)
# ---------------------------------------------------------------------------
DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DEMO_DIR)

from setup_db import setup as setup_database  # noqa: E402
print("\n  Setting up local SQLite database...")
setup_database()

# ---------------------------------------------------------------------------
# Step B: Patch imports so the Lambda handlers use our local DB module
#         instead of the AWS-dependent shared/db.py
# ---------------------------------------------------------------------------
SERVICES_DIR = os.path.join(os.path.dirname(DEMO_DIR), "services")
sys.path.insert(0, SERVICES_DIR)

# Import local DB module and monkey-patch it into shared.db before handlers load
import db_local  # noqa: E402

# Create a fake 'shared' package so "from shared.db import ..." works
shared_pkg = types.ModuleType("shared")
shared_pkg.__path__ = []  # mark as package
sys.modules["shared"] = shared_pkg
sys.modules["shared.db"] = db_local

# Import the real shared.models from the services directory
import importlib.util  # noqa: E402
models_spec = importlib.util.spec_from_file_location(
    "shared.models",
    os.path.join(SERVICES_DIR, "shared", "models.py"),
)
models_mod = importlib.util.module_from_spec(models_spec)
sys.modules["shared.models"] = models_mod
shared_pkg.models = models_mod
shared_pkg.db = db_local
models_spec.loader.exec_module(models_mod)

# Now import the Lambda handlers (they will use our patched shared.db)
from claims_get.handler import handler as get_handler       # noqa: E402
from claims_create.handler import handler as create_handler  # noqa: E402
from claims_update.handler import handler as update_handler  # noqa: E402
from claims_delete.handler import handler as delete_handler  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SEPARATOR = "=" * 70


def print_step(step_num, title, description):
    """Print a formatted step header."""
    print("\n" + SEPARATOR)
    print("  STEP %d: %s" % (step_num, title))
    print(SEPARATOR)
    print(textwrap.indent(textwrap.dedent(description).strip(), "  "))
    print()


def print_response(response):
    """Pretty-print a Lambda response."""
    status = response.get("statusCode", "???")
    body = json.loads(response.get("body", "{}"))
    print("  HTTP Status: %s" % status)
    print("  Response Body:")
    for line in json.dumps(body, indent=4, default=str).split("\n"):
        print("    " + line)
    print()


def make_event(method="GET", path_params=None, query_params=None,
               body=None, user_id="demo-user-001"):
    """Build a simulated API Gateway proxy event."""
    return {
        "httpMethod": method,
        "pathParameters": path_params,
        "queryStringParameters": query_params,
        "body": json.dumps(body) if body else None,
        "requestContext": {
            "authorizer": {
                "claims": {"sub": user_id}
            }
        },
    }


# ---------------------------------------------------------------------------
# Demo Flow
# ---------------------------------------------------------------------------
def main():
    print("\n" + "#" * 70)
    print("  UNEMPLOYMENT CLAIMS SYSTEM - LOCAL DEMO")
    print("  Modernized from COBOL (UNEMPCLM.cbl / GETCLAIM.cbl) to AWS Lambda")
    print("#" * 70)

    # ------------------------------------------------------------------
    # STEP 1: READ the seed data that was loaded from OUTCLAIM.txt
    # ------------------------------------------------------------------
    print_step(1, "READ - Get Existing Claim (seed data)", """
        This reads the January 2017 claim record that was loaded from
        the original COBOL output file (OUTCLAIM.txt) during database
        seeding. This is equivalent to the COBOL command:
            READ CLAIMS-FILE KEY IS '01012017'
    """)

    response = get_handler(
        make_event(method="GET", path_params={"period_key": "01012017"}),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 2: CREATE a new claim for February 2017
    # ------------------------------------------------------------------
    print_step(2, "CREATE - Insert New Claim", """
        This creates a new filing period (February 2017) with demographic
        breakdown data. The system will:
          - Validate all business rules (R15-R18)
          - Check for duplicate records (R09)
          - Perform a read-back confirmation (R07)
          - Log the operation to the audit trail (R12)
        Equivalent COBOL command: GETCLAIM Insert (I)
    """)

    # Counts are crafted so cross-category totals match (R15):
    # age total = race total = gender total = 5000
    new_claim_body = {
        "period_key": "02012017",
        "region_code": "US-CA",
        "counts": {
            # Age breakdown (total = 5000)
            "age_ina": 0,
            "age_under_22": 200,
            "age_22_24": 500,
            "age_25_34": 1200,
            "age_35_44": 1000,
            "age_45_54": 800,
            "age_55_59": 500,
            "age_60_64": 400,
            "age_65_over": 400,
            # Ethnicity (total = 5000)
            "eth_ina": 0,
            "eth_hispanic_latino": 1500,
            "eth_not_hispanic_latino": 3500,
            # Race breakdown (total = 5000)
            "race_ina": 0,
            "race_white": 3000,
            "race_asian": 500,
            "race_black": 1000,
            "race_native_american": 300,
            "race_pacific_islander": 200,
            # Gender breakdown (total = 5000)
            "gender_ina": 0,
            "gender_female": 2400,
            "gender_male": 2600,
            # Industry (does not need to match other totals)
            "ind_ina": 0,
            "ind_wholesale_trade": 100,
            "ind_transportation": 200,
            "ind_construction": 800,
            "ind_finance_insurance": 150,
            "ind_manufacturing": 600,
            "ind_agriculture": 50,
            "ind_public_admin": 100,
            "ind_utilities": 30,
            "ind_accommodation_food": 700,
            "ind_information": 120,
            "ind_professional_tech": 300,
            "ind_real_estate": 80,
            "ind_other_services": 250,
            "ind_management": 60,
            "ind_educational": 200,
            "ind_mining": 20,
            "ind_health_care": 500,
            "ind_arts_entertainment": 150,
            "ind_admin_support": 400,
            "ind_retail_trade": 190,
        },
    }

    response = create_handler(
        make_event(method="POST", body=new_claim_body),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 3: READ the newly created claim back
    # ------------------------------------------------------------------
    print_step(3, "READ - Verify Created Claim", """
        Read back the February 2017 record we just created to confirm
        it was stored correctly in the database.
    """)

    response = get_handler(
        make_event(method="GET", path_params={"period_key": "02012017"}),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 4: UPDATE the claim with revised numbers
    # ------------------------------------------------------------------
    print_step(4, "UPDATE - Revise Claim Data (Temporal Versioning)", """
        Update the February 2017 claim with revised numbers. Unlike the
        original COBOL system which used destructive REWRITE, this creates
        a NEW version of the record. The old version is preserved with a
        timestamp, so we have a full amendment history.
        Equivalent COBOL command: GETCLAIM Update (U)
    """)

    updated_counts = new_claim_body["counts"].copy()
    updated_counts["age_25_34"] = 1400  # revised up by 200
    updated_counts["age_35_44"] = 800   # revised down by 200
    updated_counts["race_white"] = 3200  # revised up by 200
    updated_counts["race_black"] = 800   # revised down by 200
    updated_counts["gender_female"] = 2600  # revised up by 200
    updated_counts["gender_male"] = 2400    # revised down by 200

    response = update_handler(
        make_event(
            method="PUT",
            path_params={"period_key": "02012017"},
            body={"counts": updated_counts, "region_code": "US-CA"},
        ),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 5: READ the updated record
    # ------------------------------------------------------------------
    print_step(5, "READ - Verify Updated Claim", """
        Read back February 2017 to see the updated values. The old
        version still exists in the database for audit purposes.
    """)

    response = get_handler(
        make_event(method="GET", path_params={"period_key": "02012017"}),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 6: RANGE QUERY - list all periods
    # ------------------------------------------------------------------
    print_step(6, "RANGE QUERY - List All Periods (Age Category)", """
        Retrieve all filing periods with age breakdown. This is
        equivalent to the COBOL sequential read:
            START CLAIMS-FILE KEY >= '01011900'
            READ NEXT ... (repeat)
        The new system supports filtering by demographic category
        and can return up to 1000 records (vs COBOL's 200 limit).
    """)

    response = get_handler(
        make_event(
            method="GET",
            query_params={"start": "01011900", "count": "10", "category": "age"},
        ),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 7: DELETE the February claim
    # ------------------------------------------------------------------
    print_step(7, "DELETE - Soft Delete Claim", """
        Delete the February 2017 record. Unlike the original COBOL
        DELETE which permanently removed data, this performs a soft
        delete: the record is marked inactive but preserved for audit.
        The deleted data is captured in the audit log before removal.
        Equivalent COBOL command: GETCLAIM Delete (D)
    """)

    response = delete_handler(
        make_event(
            method="DELETE",
            path_params={"period_key": "02012017"},
        ),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 8: Confirm deletion
    # ------------------------------------------------------------------
    print_step(8, "READ - Confirm Deletion", """
        Attempt to read the deleted February 2017 record. This should
        return a 404 NOT FOUND since the record is no longer active.
    """)

    response = get_handler(
        make_event(method="GET", path_params={"period_key": "02012017"}),
        None,
    )
    print_response(response)

    # ------------------------------------------------------------------
    # STEP 9: Show audit trail
    # ------------------------------------------------------------------
    print_step(9, "AUDIT TRAIL - Review All Operations", """
        Query the audit log to show every operation performed during
        this demo. This is a NEW capability -- the original COBOL
        system had no audit trail. Each entry records who performed
        the operation, when, and cryptographic hashes of the data
        before and after the change.
    """)

    with db_local.get_cursor(readonly=True) as cur:
        cur.execute("""
            SELECT operation, period_key, user_id, timestamp_utc,
                   before_hash, after_hash
            FROM claim_audit_log
            ORDER BY timestamp_utc
        """)
        rows = cur.fetchall()

    print("  %-10s %-10s %-20s %-12s %-12s" % ("Operation", "Period", "User", "Before Hash", "After Hash"))
    print("  %s %s %s %s %s" % ("-" * 10, "-" * 10, "-" * 20, "-" * 12, "-" * 12))
    for row in rows:
        bh = (row["before_hash"] or "---")[:10]
        ah = (row["after_hash"] or "---")[:10]
        print("  %-10s %-10s %-20s %-12s %-12s" % (row["operation"], row["period_key"], row["user_id"], bh, ah))

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    print("\n" + "#" * 70)
    print("  DEMO COMPLETE")
    print("#" * 70)
    print("""
  Summary of operations demonstrated:
    1. READ   - Retrieved seed data (from original COBOL OUTCLAIM.txt)
    2. CREATE - Inserted new claim with full validation (R07, R09, R12, R15-R18)
    3. READ   - Verified created record
    4. UPDATE - Revised claim with temporal versioning (old version preserved)
    5. READ   - Verified updated record
    6. RANGE  - Listed all periods filtered by demographic category
    7. DELETE - Soft-deleted claim (data preserved for audit)
    8. READ   - Confirmed deletion (404 response)
    9. AUDIT  - Reviewed immutable audit trail (new capability vs COBOL)
    """)


if __name__ == "__main__":
    main()
