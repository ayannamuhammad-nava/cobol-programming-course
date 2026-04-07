"""
Lambda handler for claim creation (Insert).
Replaces GETCLAIM.cbl Insert (I) command with write-then-readback confirmation.

COBOL equivalent:
  GETCLAIM 4000-CLAIM-INSERT: WRITE then READ to confirm
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

import sys
sys.path.insert(0, "/opt/python")

from shared.db import get_connection
from shared.models import (
    ALL_COUNT_FIELDS,
    ClaimPeriod,
    AuditEntry,
    period_key_to_date,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """
    Entry point for POST /claims

    Request body:
    {
        "period_key": "01012017",
        "region_code": "US-NY",
        "counts": {
            "age_under_22": 400,
            "age_22_24": 1000,
            ...
        }
    }
    """
    body = json.loads(event.get("body", "{}"))
    user_id = _extract_user_id(event)

    period_key = body.get("period_key", "")
    counts = body.get("counts", {})
    region_code = body.get("region_code")

    # Build and validate the claim
    claim = ClaimPeriod(
        period_key=period_key,
        period_date=period_key_to_date(period_key) if len(period_key) == 8 else None,
        counts=counts,
        region_code=region_code,
    )

    errors = claim.validate()
    if errors:
        return {
            "statusCode": 400,
            "body": json.dumps({"errors": errors}),
        }

    # R09: Duplicate check (replaces VSAM DUPREC status 22)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM claims_period WHERE period_key = %s AND is_current = TRUE",
                (period_key,),
            )
            if cur.fetchone():
                return {
                    "statusCode": 409,
                    "body": json.dumps({
                        "error": "DUPLICATE_RECORD",
                        "message": f"Record already exists for period {period_key}",
                    }),
                }

            # Insert period record
            period_id = uuid4()
            now = datetime.utcnow()

            cur.execute(
                """
                INSERT INTO claims_period
                    (id, period_key, period_date, region_code, is_current, effective_from)
                VALUES (%s, %s, %s, %s, TRUE, %s)
                """,
                (str(period_id), period_key, claim.period_date, region_code, now),
            )

            # Insert demographic counts
            for field_name in ALL_COUNT_FIELDS:
                count_value = counts.get(field_name, 0)
                # Derive category_type from field name prefix
                category_type = field_name.split("_")[0]
                if category_type in ("eth", "ind"):
                    category_type = {"eth": "ethnicity", "ind": "industry"}.get(
                        category_type, category_type
                    )

                cur.execute(
                    """
                    INSERT INTO claim_demographic_counts
                        (id, period_id, category_type, category_code, count)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(uuid4()), str(period_id), category_type, field_name, count_value),
                )

            # R07: Read-back confirmation (replaces COBOL read-after-write)
            cur.execute(
                "SELECT period_key, period_date FROM claims_period WHERE id = %s",
                (str(period_id),),
            )
            readback = cur.fetchone()

            if not readback or readback[0] != period_key:
                raise RuntimeError(
                    f"R07 read-back failed: expected {period_key}, got {readback}"
                )

            # Audit log entry (R12: capture every write)
            after_hash = hashlib.sha256(
                json.dumps(counts, sort_keys=True).encode()
            ).hexdigest()

            cur.execute(
                """
                INSERT INTO claim_audit_log
                    (id, user_id, operation, period_key, timestamp_utc, before_hash, after_hash)
                VALUES (%s, %s, 'INSERT', %s, %s, NULL, %s)
                """,
                (str(uuid4()), user_id, period_key, now, after_hash),
            )

    logger.info("Created claim: period=%s user=%s", period_key, user_id)

    return {
        "statusCode": 201,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "id": str(period_id),
            "period_key": period_key,
            "period_date": str(claim.period_date),
            "status": "CREATED",
            "readback_confirmed": True,
        }),
    }


def _extract_user_id(event: dict) -> str:
    """Extract authenticated user ID from Cognito JWT claims."""
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    return claims.get("sub", "system")
