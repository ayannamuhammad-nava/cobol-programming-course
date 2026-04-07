"""
Data models and validation for unemployment claims system.
Maps the 43-field COBOL record structure to Python dataclasses with proper validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

# Period key format: MMDDYYYY where DD is always 01
PERIOD_KEY_PATTERN = re.compile(r"^(0[1-9]|1[0-2])01(19|20)\d{2}$")

# Maximum realistic claim count per field (configurable threshold for R18)
MAX_CLAIM_COUNT = 10_000_000

DEMOGRAPHIC_CATEGORIES = {
    "age": [
        "age_ina", "age_under_22", "age_22_24", "age_25_34",
        "age_35_44", "age_45_54", "age_55_59", "age_60_64", "age_65_over",
    ],
    "ethnicity": [
        "eth_ina", "eth_hispanic_latino", "eth_not_hispanic_latino",
    ],
    "industry": [
        "ind_ina", "ind_wholesale_trade", "ind_transportation",
        "ind_construction", "ind_finance_insurance", "ind_manufacturing",
        "ind_agriculture", "ind_public_admin", "ind_utilities",
        "ind_accommodation_food", "ind_information", "ind_professional_tech",
        "ind_real_estate", "ind_other_services", "ind_management",
        "ind_educational", "ind_mining", "ind_health_care",
        "ind_arts_entertainment", "ind_admin_support", "ind_retail_trade",
    ],
    "race": [
        "race_ina", "race_white", "race_asian",
        "race_black", "race_native_american", "race_pacific_islander",
    ],
    "gender": [
        "gender_ina", "gender_female", "gender_male",
    ],
}

# Flat list of all count field names
ALL_COUNT_FIELDS = [
    field_name
    for fields in DEMOGRAPHIC_CATEGORIES.values()
    for field_name in fields
]


@dataclass
class ClaimPeriod:
    """Represents a single unemployment claims filing period."""

    period_key: str
    period_date: date
    counts: dict[str, int]
    id: UUID = field(default_factory=uuid4)
    region_code: Optional[str] = None
    is_current: bool = True
    effective_from: datetime = field(default_factory=datetime.utcnow)
    effective_to: Optional[datetime] = None

    def validate(self) -> list[str]:
        """Run all validation rules. Returns list of error messages (empty = valid)."""
        errors = []

        # R16: Valid period key format
        if not PERIOD_KEY_PATTERN.match(self.period_key):
            errors.append(
                f"R16: Invalid period key '{self.period_key}'. "
                "Must be MMDDYYYY with DD=01."
            )

        # R17: Non-negative claim counts
        for field_name, value in self.counts.items():
            if value < 0:
                errors.append(
                    f"R17: Negative count for {field_name}: {value}"
                )

        # R18: Realistic ceiling
        for field_name, value in self.counts.items():
            if value > MAX_CLAIM_COUNT:
                errors.append(
                    f"R18: Count for {field_name} ({value}) exceeds "
                    f"threshold {MAX_CLAIM_COUNT}"
                )

        # R15: Cross-category totals validation
        totals = {}
        for category, fields in DEMOGRAPHIC_CATEGORIES.items():
            if category == "industry":
                continue  # Industry totals may differ from other categories
            total = sum(self.counts.get(f, 0) for f in fields)
            totals[category] = total

        category_totals = list(totals.values())
        if category_totals and len(set(category_totals)) > 1:
            detail = ", ".join(f"{k}={v}" for k, v in totals.items())
            errors.append(
                f"R15: Cross-category totals mismatch: {detail}"
            )

        return errors


@dataclass
class ClaimCommand:
    """Represents a single claim operation command (replaces SYSIN batch input)."""

    operation: str  # R, I, U, D
    period_key: str
    num_records: int = 1
    category: Optional[str] = None
    data: Optional[dict[str, int]] = None

    def validate(self) -> list[str]:
        errors = []

        # R01: Valid operation code
        if self.operation not in ("R", "I", "U", "D"):
            errors.append(
                f"R01: Invalid operation '{self.operation}'. "
                "Must be R, I, U, or D."
            )

        # R02: Record count > 0
        if self.num_records < 1:
            errors.append(f"R02: num_records must be > 0, got {self.num_records}")

        # R03/R04: Valid category for range queries
        if self.num_records > 1 and self.category not in DEMOGRAPHIC_CATEGORIES:
            errors.append(
                f"R03: Invalid category '{self.category}' for range query. "
                f"Must be one of: {list(DEMOGRAPHIC_CATEGORIES.keys())}"
            )

        return errors


@dataclass
class AuditEntry:
    """Immutable audit log record for every write operation."""

    user_id: str
    operation: str
    period_key: str
    timestamp_utc: datetime = field(default_factory=datetime.utcnow)
    before_hash: Optional[str] = None
    after_hash: Optional[str] = None
    id: UUID = field(default_factory=uuid4)


def period_key_to_date(period_key: str) -> date:
    """Convert MMDDYYYY period key to a date object."""
    month = int(period_key[0:2])
    year = int(period_key[4:8])
    return date(year, month, 1)


def date_to_period_key(d: date) -> str:
    """Convert a date to MMDDYYYY period key format."""
    return f"{d.month:02d}01{d.year:04d}"
