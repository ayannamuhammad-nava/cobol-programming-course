"""
Lambda handler for claim read operations.
Replaces GETCLAIM.cbl Read (R) command -- both single-key lookup and range scan.

COBOL equivalent:
  - Single record: Direct keyed VSAM READ by 8-char period key
  - Range scan: START at key, READ NEXT up to N records sequentially
"""
from __future__ import annotations

import json
import logging
from typing import Any

import sys
sys.path.insert(0, "/opt/python")  # Lambda layer path

from shared.db import get_cursor
from shared.models import DEMOGRAPHIC_CATEGORIES

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context: Any) -> dict:
    """
    Entry point for GET /claims/{period_key} and GET /claims?start={key}&count={n}&category={cat}

    Path parameters:
        period_key: 8-char MMDDYYYY key for single record lookup

    Query parameters (range mode):
        start: Starting period key
        count: Number of records (max 1000, replaces COBOL 200 limit)
        category: Demographic category filter (age, ethnicity, industry, race, gender)
    """
    http_method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    period_key = path_params.get("period_key")

    if period_key:
        return _get_by_key(period_key)
    else:
        return _get_range(
            start_key=query_params.get("start", "01011900"),
            count=min(int(query_params.get("count", "10")), 1000),
            category=query_params.get("category"),
        )


def _get_by_key(period_key: str) -> dict:
    """
    Single record lookup by period key.
    Returns all demographic counts for the specified filing period.
    Equivalent to COBOL: READ CLAIMS-FILE KEY IS UNEMP-CLAIM-KEY
    """
    with get_cursor(readonly=True) as cur:
        cur.execute(
            """
            SELECT
                cp.period_key,
                cp.period_date,
                cp.region_code,
                cp.effective_from,
                cdc.category_type,
                cdc.category_code,
                cdc.count
            FROM claims_period cp
            JOIN claim_demographic_counts cdc ON cdc.period_id = cp.id
            WHERE cp.period_key = %s
              AND cp.is_current = TRUE
            ORDER BY cdc.category_type, cdc.category_code
            """,
            (period_key,),
        )
        rows = cur.fetchall()

    if not rows:
        return {
            "statusCode": 404,
            "body": json.dumps({
                "error": "NOT_FOUND",
                "message": f"No claim record found for period {period_key}",
            }),
        }

    # Build the detail view (equivalent to COBOL single-record "Directory View")
    record = {
        "period_key": rows[0]["period_key"],
        "period_date": str(rows[0]["period_date"]),
        "region_code": rows[0]["region_code"],
        "effective_from": str(rows[0]["effective_from"]),
        "demographics": {},
    }

    for row in rows:
        cat_type = row["category_type"]
        if cat_type not in record["demographics"]:
            record["demographics"][cat_type] = {}
        record["demographics"][cat_type][row["category_code"]] = row["count"]

    logger.info("GetByKey: period=%s found=%d demographic rows", period_key, len(rows))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(record, default=str),
    }


def _get_range(start_key: str, count: int, category: str | None) -> dict:
    """
    Range scan starting at a period key.
    Returns multiple records in tabular format.
    Equivalent to COBOL: START CLAIMS-FILE KEY >= start, then READ NEXT * N
    """
    if category and category not in DEMOGRAPHIC_CATEGORIES:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "INVALID_CATEGORY",
                "message": f"Category must be one of: {list(DEMOGRAPHIC_CATEGORIES.keys())}",
            }),
        }

    with get_cursor(readonly=True) as cur:
        query = """
            SELECT
                cp.period_key,
                cp.period_date,
                cdc.category_type,
                cdc.category_code,
                cdc.count
            FROM claims_period cp
            JOIN claim_demographic_counts cdc ON cdc.period_id = cp.id
            WHERE cp.period_key >= %s
              AND cp.is_current = TRUE
        """
        params: list = [start_key]

        if category:
            query += " AND cdc.category_type = %s"
            params.append(category)

        query += " ORDER BY cp.period_key, cdc.category_type, cdc.category_code"

        cur.execute(query, params)
        rows = cur.fetchall()

    # Group by period_key, limit to `count` periods
    periods: dict[str, dict] = {}
    for row in rows:
        pk = row["period_key"]
        if pk not in periods:
            if len(periods) >= count:
                break
            periods[pk] = {
                "period_key": pk,
                "period_date": str(row["period_date"]),
                "demographics": {},
            }
        cat_type = row["category_type"]
        if cat_type not in periods[pk]["demographics"]:
            periods[pk]["demographics"][cat_type] = {}
        periods[pk]["demographics"][cat_type][row["category_code"]] = row["count"]

    logger.info("GetRange: start=%s count=%d found=%d periods", start_key, count, len(periods))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "count": len(periods),
            "records": list(periods.values()),
        }, default=str),
    }
