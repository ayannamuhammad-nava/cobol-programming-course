"""
Lambda handler for OPA policy validation.
Enforces all business rules (R01-R20) as a policy-as-code layer.

This replaces the scattered EVALUATE/IF statements and ABENDs in COBOL
with a centralized, independently deployable validation engine.
"""

import json
import logging
from typing import Any

import sys
sys.path.insert(0, "/opt/python")

from shared.models import (
    DEMOGRAPHIC_CATEGORIES,
    MAX_CLAIM_COUNT,
    PERIOD_KEY_PATTERN,
    ClaimCommand,
    ClaimPeriod,
    period_key_to_date,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# R20: Role-based write access
WRITE_OPERATIONS = {"I", "U", "D"}
WRITE_ROLES = {"claims_writer", "claims_admin"}
ADMIN_ROLES = {"claims_admin"}


def handler(event: dict, context: Any) -> dict:
    """
    Validation entry point called by Step Functions before any operation.

    Input event:
    {
        "operation": "I",
        "period_key": "01012017",
        "num_records": 1,
        "category": null,
        "counts": { ... },
        "user_roles": ["claims_writer"],
        "user_id": "user-123"
    }

    Returns:
    {
        "valid": true/false,
        "errors": [...],
        "warnings": [...]
    }
    """
    errors = []
    warnings = []

    operation = event.get("operation", "")
    period_key = event.get("period_key", "")
    num_records = event.get("num_records", 1)
    category = event.get("category")
    counts = event.get("counts", {})
    user_roles = set(event.get("user_roles", []))

    # --- Command-level validation ---

    # R01: Valid operation code
    if operation not in ("R", "I", "U", "D"):
        errors.append({
            "rule": "R01",
            "severity": "ERROR",
            "message": f"Invalid operation '{operation}'. Must be R, I, U, or D.",
        })

    # R02: Record count > 0
    if num_records < 1:
        errors.append({
            "rule": "R02",
            "severity": "ERROR",
            "message": f"num_records must be > 0, got {num_records}",
        })

    # R03/R04: Valid category for range queries
    if num_records > 1 and category not in DEMOGRAPHIC_CATEGORIES:
        errors.append({
            "rule": "R03",
            "severity": "ERROR",
            "message": f"Range query requires valid category. Got '{category}', "
                       f"expected one of: {list(DEMOGRAPHIC_CATEGORIES.keys())}",
        })

    # R16: Valid period key format
    if period_key and not PERIOD_KEY_PATTERN.match(period_key):
        errors.append({
            "rule": "R16",
            "severity": "ERROR",
            "message": f"Invalid period key '{period_key}'. Must be MMDDYYYY with DD=01.",
        })

    # R20: Role-based write access
    if operation in WRITE_OPERATIONS and not user_roles.intersection(WRITE_ROLES):
        errors.append({
            "rule": "R20",
            "severity": "ERROR",
            "message": f"Write operation '{operation}' requires role: {WRITE_ROLES}. "
                       f"User has: {user_roles}",
        })

    # --- Data-level validation (only for write operations with counts) ---

    if counts and operation in ("I", "U"):
        # R17: Non-negative integers
        for field_name, value in counts.items():
            if not isinstance(value, int) or value < 0:
                errors.append({
                    "rule": "R17",
                    "severity": "ERROR",
                    "message": f"Count for '{field_name}' must be a non-negative integer, got {value}",
                })

        # R18: Realistic ceiling
        for field_name, value in counts.items():
            if isinstance(value, int) and value > MAX_CLAIM_COUNT:
                errors.append({
                    "rule": "R18",
                    "severity": "ERROR",
                    "message": f"Count for '{field_name}' ({value}) exceeds threshold {MAX_CLAIM_COUNT}",
                })

        # R15: Cross-category totals
        totals = {}
        for cat_name, fields in DEMOGRAPHIC_CATEGORIES.items():
            if cat_name == "industry":
                continue
            total = sum(counts.get(f, 0) for f in fields)
            totals[cat_name] = total

        total_values = list(totals.values())
        if total_values and len(set(total_values)) > 1:
            detail = ", ".join(f"{k}={v}" for k, v in totals.items())
            errors.append({
                "rule": "R15",
                "severity": "ERROR",
                "message": f"Cross-category totals mismatch: {detail}. "
                           "sum(age) must equal sum(race) must equal sum(gender).",
            })

        # R19: INA counts should be present
        ina_fields = [f for f in counts if f.endswith("_ina")]
        if not ina_fields:
            warnings.append({
                "rule": "R19",
                "severity": "WARNING",
                "message": "No INA (not-applicable) counts provided. "
                           "INA fields should be included in submissions.",
            })

    is_valid = len(errors) == 0

    logger.info(
        "Validation: op=%s key=%s valid=%s errors=%d warnings=%d",
        operation, period_key, is_valid, len(errors), len(warnings),
    )

    return {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
    }
