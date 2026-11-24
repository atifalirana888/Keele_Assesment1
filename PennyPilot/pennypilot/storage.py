"""Versioned JSON persistence with validation and atomic replacement.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
The student must review, understand and acknowledge this use in their submission.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from decimal import Decimal

from .models import (
    EXPENSE_CATEGORIES, Transaction, ValidationError, parse_money, validate_month,
    money_text,
)

SCHEMA_VERSION = 1


class DataFileError(Exception):
    """Readable message for I/O, corrupt-file, or schema failures."""


def load_data(path: Path) -> tuple[dict[str, Transaction], dict[tuple[str, str], Decimal]]:
    """Load and validate all records before returning anything to the caller."""
    if not path.exists():
        return {}, {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataFileError(f"Cannot read data file '{path}': {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise DataFileError("Unsupported or missing JSON schema version (expected 1).")
    if not isinstance(data.get("transactions"), list) or not isinstance(data.get("budgets"), list):
        raise DataFileError("JSON must contain 'transactions' and 'budgets' lists.")
    transactions: dict[str, Transaction] = {}
    budgets: dict[tuple[str, str], Decimal] = {}
    try:
        for number, raw in enumerate(data["transactions"], start=1):
            transaction = Transaction.from_dict(raw)
            if transaction.id in transactions:
                raise ValidationError(f"Duplicate transaction ID on record {number}.")
            transactions[transaction.id] = transaction
        for number, raw in enumerate(data["budgets"], start=1):
            if not isinstance(raw, dict):
                raise ValidationError(f"Budget {number} must be an object.")
            month = validate_month(raw.get("month"))
            category = raw.get("category")
            if category not in EXPENSE_CATEGORIES:
                raise ValidationError(f"Invalid budget category on record {number}.")
            amount = parse_money(raw.get("amount"))
            key = month, category
            if key in budgets:
                raise ValidationError(f"Duplicate budget on record {number}.")
            budgets[key] = amount
    except ValidationError as exc:
        raise DataFileError(f"Invalid saved data: {exc}") from exc
    return transactions, budgets


def save_data(
    path: Path,
    transactions: dict[str, Transaction],
    budgets: dict[tuple[str, str], Decimal],
) -> None:
    """Write JSON to a temporary sibling and replace target only after a full write."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "transactions": [t.to_dict() for t in sorted(transactions.values(), key=lambda t: (t.date, t.id))],
        "budgets": [
            {"month": month, "category": category, "amount": money_text(amount)}
            for (month, category), amount in sorted(budgets.items())
        ],
    }
    temp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except OSError as exc:
        raise DataFileError(f"Cannot save data file '{path}': {exc}") from exc
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
