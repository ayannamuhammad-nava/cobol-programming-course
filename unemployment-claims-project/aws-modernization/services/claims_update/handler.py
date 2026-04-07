"""
Lambda handler for claim update operations.
Replaces GETCLAIM.cbl Update (U) command with temporal versioning.

COBOL equivalent:
  GETCLAIM 5000-CLAIM-UPDATE: READ, REWRITE, READ (confirm)

Key improvement: Instead of destructive REWRITE, this creates a new version
of the record. The old version is preserved with effective_to timestamp.
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
from shared.models import ALL_COUNT_FIELDS, ClaimPeriod, period_key_to_date

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """
    Entry point for PUT /claims/{period_key}

    Request body:
    {
        "counts": {
            "age_under_22": 400,
            "age_22_24": 1000,
            ...
        },
        "region_code": "US-NY"
    }
    """
    path_params = event.get("pathParameters") or {}
    period_key = path_params.get("period_key", "")
    body = json.loads(event.get("body", "{}"))
    user_id = _extract_user_id(event)
    counts = body.get("counts", {})
    region_code = body.get("region_code")

    # Validate the updated claim data
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

    now = datetime.utcnow()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # R06: Record must exist before update (replaces COBOL read-before-rewrite)
            cur.execute(
                """
                SELECT id, period_key, region_code
                FROM claims_period
                WHERE period_key = %s AND is_current = TRUE
                FOR UPDATE
                """,
                (period_key,),
            )
            existing = cur.fetchone()

            if not existing:
                return {
                    "statusCode": 404,
                    "body": json.dumps({
                        "error": "NOT_FOUND",
                        "message": f"No current record for period {period_key}",
                    }),
                }

            old_period_id = existing[0]

            # Capture before-state hash for audit
            cur.execute(
                """
                SELECT category_code, count
                FROM claim_demographic_counts
                WHERE period_id = %s
                ORDER BY category_code
                """,
                (str(old_period_id),),
            )
            old_counts = {row[0]: row[1] for row in cur.fetchall()}
            before_hash = hashlib.sha256(
                json.dumps(old_counts, sort_keys=True).encode()
            ).hexdigest()

            # Close out old version (temporal: set effective_to, mark not current)
            cur.execute(
                """
                UPDATE claims_period
                SET is_current = FALSE, effective_to = %s
                WHERE id = %s
                """,
                (now, str(old_period_id)),
            )

            # Create new version
            new_period_id = uuid4()
            cur.execute(
                """
                INSERT INTO claims_period
                    (id, period_key, period_date, region_code, is_current, effective_from)
                VALUES (%s, %s, %s, %s, TRUE, %s)
                """,
                (
                    str(new_period_id),
                    period_key,
                    claim.period_date,
                    region_code or existing[2],
                    now,
                ),
            )

            # Insert new demographic counts
            for field_name in ALL_COUNT_FIELDS:
                count_value = counts.get(field_name, 0)
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
                    (str(uuid4()), str(new_period_id), category_type, field_name, count_value),
                )

            # R08: Read-back confirmation
            cur.execute(
                "SELECT period_key FROM claims_period WHERE id = %s",
                (str(new_period_id),),
            )
            readback = cur.fetchone()
            if not readback or readback[0] != period_key:
                raise RuntimeError(
                    f"R08 read-back failed: expected {period_key}, got {readback}"
                )

            # Audit log
            after_hash = hashlib.sha256(
                json.dumps(counts, sort_keys=True).encode()
            ).hexdigest()

            cur.execute(
                """
                INSERT INTO claim_audit_log
                    (id, user_id, operation, period_key, timestamp_utc, before_hash, after_hash)
                VALUES (%s, %s, 'UPDATE', %s, %s, %s, %s)
                """,
                (str(uuid4()), user_id, period_key, now, before_hash, after_hash),
            )

    logger.info("Updated claim: period=%s user=%s", period_key, user_id)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "id": str(new_period_id),
            "period_key": period_key,
            "status": "UPDATED",
            "previous_version_id": str(old_period_id),
            "readback_confirmed": True,
        }),
    }


def _extract_user_id(event: dict) -> str:
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    return claims.get("sub", "system")
