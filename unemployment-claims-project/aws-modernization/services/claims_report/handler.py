"""
Lambda handler for report generation.
Replaces UNEMPCLM.cbl report writing logic that produced OUTCLAIM.txt.

Generates both:
  - JSON summary (for QuickSight / programmatic consumption)
  - Text report (backward-compatible OUTCLAIM.txt equivalent)
"""

import io
import json
import logging
from datetime import datetime
from typing import Any

import boto3

import sys
sys.path.insert(0, "/opt/python")

from shared.db import get_cursor
from shared.models import DEMOGRAPHIC_CATEGORIES

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
REPORT_BUCKET = "unemployment-claims-reports"


def handler(event: dict, context: Any) -> dict:
    """
    Entry point for POST /reports/generate

    Input:
    {
        "start_period": "01012017",
        "end_period": "12012017",
        "category": "age",
        "format": "json"  // or "text"
    }
    """
    start_period = event.get("start_period", "01011900")
    end_period = event.get("end_period", "12019999")
    category = event.get("category")
    output_format = event.get("format", "json")

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
            WHERE cp.is_current = TRUE
              AND cp.period_key >= %s
              AND cp.period_key <= %s
        """
        params = [start_period, end_period]

        if category and category in DEMOGRAPHIC_CATEGORIES:
            query += " AND cdc.category_type = %s"
            params.append(category)

        query += " ORDER BY cp.period_key, cdc.category_type, cdc.category_code"

        cur.execute(query, params)
        rows = cur.fetchall()

    # Build structured report data
    periods = {}
    for row in rows:
        pk = row["period_key"]
        if pk not in periods:
            periods[pk] = {
                "period_key": pk,
                "period_date": str(row["period_date"]),
                "demographics": {},
            }
        cat_type = row["category_type"]
        if cat_type not in periods[pk]["demographics"]:
            periods[pk]["demographics"][cat_type] = {}
        periods[pk]["demographics"][cat_type][row["category_code"]] = row["count"]

    if output_format == "text":
        report_content = _generate_text_report(periods, category)
        content_type = "text/plain"
    else:
        report_content = json.dumps({
            "generated_at": datetime.utcnow().isoformat(),
            "start_period": start_period,
            "end_period": end_period,
            "category_filter": category,
            "total_periods": len(periods),
            "records": list(periods.values()),
        }, default=str, indent=2)
        content_type = "application/json"

    # Upload to S3
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ext = "txt" if output_format == "text" else "json"
    s3_key = f"reports/{timestamp}_claims_report.{ext}"

    s3.put_object(
        Bucket=REPORT_BUCKET,
        Key=s3_key,
        Body=report_content.encode("utf-8"),
        ContentType=content_type,
    )

    # Generate pre-signed download URL (valid 1 hour)
    download_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": REPORT_BUCKET, "Key": s3_key},
        ExpiresIn=3600,
    )

    logger.info(
        "Report generated: periods=%d format=%s s3_key=%s",
        len(periods), output_format, s3_key,
    )

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "report_key": s3_key,
            "download_url": download_url,
            "total_periods": len(periods),
            "format": output_format,
        }),
    }


def _generate_text_report(periods: dict, category: str | None) -> str:
    """
    Generate backward-compatible text report matching OUTCLAIM.txt format.
    Replicates the tabular layout from UNEMPCLM.cbl's summary view.
    """
    buf = io.StringIO()
    buf.write("=" * 80 + "\n")
    buf.write("  UNEMPLOYMENT CLAIMS DEMOGRAPHIC REPORT\n")
    buf.write(f"  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    buf.write("=" * 80 + "\n\n")

    if len(periods) == 1:
        # Detail view (single record) -- one field per line
        record = list(periods.values())[0]
        buf.write(f"  Filing Period: {record['period_key']}\n")
        buf.write(f"  Period Date:   {record['period_date']}\n")
        buf.write("-" * 50 + "\n")

        for cat_name, fields in record["demographics"].items():
            buf.write(f"\n  {cat_name.upper()}\n")
            buf.write(f"  {'Category':<40} {'Count':>10}\n")
            buf.write(f"  {'-' * 40} {'-' * 10}\n")
            for field_name, count in fields.items():
                display = field_name.replace("_", " ").title()
                buf.write(f"  {display:<40} {count:>10,}\n")
    else:
        # Tabular view (multiple records) -- columns by category
        categories_to_show = (
            [category] if category else list(DEMOGRAPHIC_CATEGORIES.keys())
        )

        for cat_name in categories_to_show:
            if cat_name not in DEMOGRAPHIC_CATEGORIES:
                continue

            fields = DEMOGRAPHIC_CATEGORIES[cat_name]
            buf.write(f"\n  {cat_name.upper()} BREAKDOWN\n")
            buf.write("-" * 80 + "\n")

            # Header row
            buf.write(f"  {'Period':<12}")
            for f in fields:
                label = f.replace(cat_name + "_", "").replace("_", " ")[:10]
                buf.write(f" {label:>10}")
            buf.write("\n")

            buf.write(f"  {'-' * 10:<12}")
            for _ in fields:
                buf.write(f" {'-' * 10}")
            buf.write("\n")

            # Data rows
            for pk, record in periods.items():
                cat_data = record.get("demographics", {}).get(cat_name, {})
                buf.write(f"  {pk:<12}")
                for f in fields:
                    val = cat_data.get(f, 0)
                    buf.write(f" {val:>10,}")
                buf.write("\n")

            buf.write("\n")

    buf.write("=" * 80 + "\n")
    buf.write("  END OF REPORT\n")
    buf.write("=" * 80 + "\n")

    return buf.getvalue()
