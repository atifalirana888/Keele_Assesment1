"""Validated domain models and money/date helpers for PennyPilot.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
The student must review, understand and acknowledge this use in their submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal, InvalidOperation
import re


EXPENSE_CATEGORIES = (
    "Food & Drink", "Groceries", "Housing", "Transport", "Shopping",
    "Entertainment", "Health", "Education", "Bills", "Other",
)
INCOME_CATEGORIES = ("Salary", "Freelance", "Gift", "Investment", "Other")
KINDS = ("income", "expense")
MAX_AMOUNT = Decimal("999999999.99")
_AMOUNT_PATTERN = re.compile(r"^\d{1,9}(?:\.\d{1,2})?$")
_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised when an input or stored domain record is invalid."""


def validate_month(month: str) -> str:
    """Return a validated YYYY-MM month string."""
    if not isinstance(month, str) or not _MONTH_PATTERN.fullmatch(month):
        raise ValidationError("Month must use YYYY-MM, for example 2026-11.")
    if not 1900 <= int(month[:4]) <= 2100:
        raise ValidationError("Year must be between 1900 and 2100.")
    return month


def validate_date(value: str) -> str:
    """Validate an actual calendar date, not only its text format."""
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise ValidationError("Date must use YYYY-MM-DD, for example 2026-11-20.")
    try:
        parsed = Date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("Enter a real calendar date.") from exc
    if not 1900 <= parsed.year <= 2100:
        raise ValidationError("Year must be between 1900 and 2100.")
    return value


def parse_money(value: str | Decimal) -> Decimal:
    """Accept positive values with at most 2 decimal places, using exact Decimals."""
    if isinstance(value, bool) or not isinstance(value, (str, Decimal)):
        raise ValidationError("Amount must be a positive number, such as 42.50.")
    text = str(value).strip()
    if not _AMOUNT_PATTERN.fullmatch(text):
        raise ValidationError("Amount must be positive with up to 2 decimal places (no currency symbol).")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ValidationError("Invalid amount.") from exc
    if amount <= 0 or amount > MAX_AMOUNT:
        raise ValidationError("Amount must be greater than 0 and no more than 999,999,999.99.")
    return amount.quantize(Decimal("0.01"))


def money_text(value: Decimal) -> str:
    """Format a Decimal for JSON / CSV without currency symbols."""
    return f"{value:.2f}"


def money_display(value: Decimal, *, currency: str = "£") -> str:
    """Format money consistently in both interfaces."""
    prefix = "−" if value < 0 else ""
    return f"{prefix}{currency}{abs(value):,.2f}"


def categories_for(kind: str) -> tuple[str, ...]:
    if kind == "income":
        return INCOME_CATEGORIES
    if kind == "expense":
        return EXPENSE_CATEGORIES
    raise ValidationError("Type must be income or expense.")


@dataclass(frozen=True, slots=True)
class Transaction:
    """Immutable transaction; changes create a validated replacement."""

    id: str
    date: str
    kind: str
    category: str
    description: str
    amount: Decimal
    note: str = ""

    @classmethod
    def create(
        cls, *, id: str, date: str, kind: str, category: str,
        description: str, amount: str | Decimal, note: str = "",
    ) -> "Transaction":
        if not isinstance(id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,40}", id):
            raise ValidationError("Invalid transaction ID in data file.")
        validate_date(date)
        if category not in categories_for(kind):
            raise ValidationError(f"Category '{category}' is not valid for {kind}.")
        if not isinstance(description, str) or not 2 <= len(description.strip()) <= 70:
            raise ValidationError("Description must be between 2 and 70 characters.")
        if not isinstance(note, str) or len(note.strip()) > 240:
            raise ValidationError("Note cannot exceed 240 characters.")
        return cls(
            id=id, date=date, kind=kind, category=category,
            description=description.strip(), amount=parse_money(amount), note=note.strip(),
        )

    @classmethod
    def from_dict(cls, record: dict) -> "Transaction":
        if not isinstance(record, dict):
            raise ValidationError("Transaction record must be an object.")
        required = {"id", "date", "kind", "category", "description", "amount"}
        if not required.issubset(record):
            raise ValidationError("Transaction record is missing required fields.")
        return cls.create(
            id=record["id"], date=record["date"], kind=record["kind"],
            category=record["category"], description=record["description"],
            amount=record["amount"], note=record.get("note", ""),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id, "date": self.date, "kind": self.kind,
            "category": self.category, "description": self.description,
            "amount": money_text(self.amount), "note": self.note,
        }
