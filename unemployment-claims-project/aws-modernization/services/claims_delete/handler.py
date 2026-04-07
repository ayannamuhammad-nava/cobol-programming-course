"""
Lambda handler for claim deletion.
Replaces GETCLAIM.cbl Delete (D) command with soft-delete and data capture.

COBOL equivalent:
  GETCLAIM 3000-CLAIM-DELETE: READ (capture data), then DELETE

Key improvement: Soft delete preserves data for audit. The record remains
in the database with is_current=FALSE and effective_to set.
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

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """
    Entry point for DELETE /claims/{period_key}

    R05: Record must exist before deletion.
    R12: Deleted record data is captured in audit log before removal.
    """
    path_params = event.get("pathParameters") or {}
    period_key = path_params.get("period_key", "")
    user_id = _extract_user_id(event)
    now = datetime.utcnow()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # R05 + R12: Read record before delete to capture its data
            cur.execute(
                """
                SELECT cp.id, cp.period_key, cp.period_date, cp.region_code
                FROM claims_period cp
                WHERE cp.period_key = %s AND cp.is_current = TRUE
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

            period_id = existing[0]

            # Capture all demographic data before deletion (R12)
            cur.execute(
                """
                SELECT category_code, count
                FROM claim_demographic_counts
                WHERE period_id = %s
                ORDER BY category_code
                """,
                (str(period_id),),
            )
            deleted_counts = {row[0]: row[1] for row in cur.fetchall()}
            before_hash = hashlib.sha256(
                json.dumps(deleted_counts, sort_keys=True).encode()
            ).hexdigest()

            # Soft delete: mark as not current, set effective_to
            cur.execute(
                """
                UPDATE claims_period
                SET is_current = FALSE, effective_to = %s
                WHERE id = %s
                """,
                (now, str(period_id)),
            )

            # Audit log with before-state captured
            cur.execute(
                """
                INSERT INTO claim_audit_log
                    (id, user_id, operation, period_key, timestamp_utc, before_hash, after_hash)
                VALUES (%s, %s, 'DELETE', %s, %s, %s, NULL)
                """,
                (str(uuid4()), user_id, period_key, now, before_hash),
            )

    logger.info("Deleted claim: period=%s user=%s", period_key, user_id)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "period_key": period_key,
            "status": "DELETED",
            "deleted_counts": deleted_counts,
            "before_hash": before_hash,
        }),
    }


def _extract_user_id(event: dict) -> str:
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    return claims.get("sub", "system")
