"""Shared application use-cases, search, sorting, aggregation, budgets, CSV export.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
The student must review, understand and acknowledge this use in their submission.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from .models import (
    EXPENSE_CATEGORIES, Transaction, ValidationError,
    parse_money, validate_month, categories_for, money_text,
)
from .storage import load_data, save_data

SORT_OPTIONS = {
    "newest": "Newest first", "oldest": "Oldest first",
    "highest": "Highest amount", "lowest": "Lowest amount",
    "category": "Category A–Z", "description": "Description A–Z",
}
ZERO = Decimal("0.00")


class FinanceService:
    """Business layer shared by command-line and Tkinter interfaces.

    Dict IDs allow average O(1) edits/deletes; list views are filtered O(n),
    Python's stable Timsort orders results O(n log n); summaries group in O(n).
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._transactions, self._budgets = load_data(self.path)

    def _commit(self, transactions: dict, budgets: dict) -> None:
        # Never change active in-memory data if a write fails.
        save_data(self.path, transactions, budgets)
        self._transactions, self._budgets = transactions, budgets

    def add_transaction(
        self, *, date: str, kind: str, category: str,
        description: str, amount: str | Decimal, note: str = "",
    ) -> Transaction:
        transaction = Transaction.create(
            id=uuid4().hex, date=date, kind=kind, category=category,
            description=description, amount=amount, note=note,
        )
        updated = self._transactions.copy()
        updated[transaction.id] = transaction
        self._commit(updated, self._budgets)
        return transaction

    def get_transaction(self, transaction_id: str) -> Transaction:
        try:
            return self._transactions[transaction_id]
        except KeyError as exc:
            raise ValidationError("Transaction not found; refresh your list.") from exc

    def edit_transaction(self, transaction_id: str, **fields) -> Transaction:
        current = self.get_transaction(transaction_id)
        valid_fields = {"date", "kind", "category", "description", "amount", "note"}
        if not fields or not set(fields).issubset(valid_fields):
            raise ValidationError("No valid fields were provided for editing.")
        values = current.to_dict()
        values.update(fields)
        replacement = Transaction.from_dict(values)
        updated = self._transactions.copy()
        updated[transaction_id] = replacement
        self._commit(updated, self._budgets)
        return replacement

    def delete_transaction(self, transaction_id: str) -> Transaction:
        transaction = self.get_transaction(transaction_id)
        updated = self._transactions.copy()
        del updated[transaction_id]
        self._commit(updated, self._budgets)
        return transaction

    def list_transactions(
        self, *, month: str | None = None, kind: str = "all",
        category: str = "all", search: str = "", sort: str = "newest",
    ) -> list[Transaction]:
        if month is not None and month != "":
            validate_month(month)
        if kind not in ("all", "income", "expense"):
            raise ValidationError("Type filter must be all, income, or expense.")
        if category != "all" and category not in (*EXPENSE_CATEGORIES, *categories_for("income")):
            raise ValidationError("Unknown category filter.")
        if sort not in SORT_OPTIONS:
            raise ValidationError("Unknown sort option.")
        needle = search.strip().casefold()
        matches = [
            t for t in self._transactions.values()
            if (not month or t.date.startswith(month + "-"))
            and (kind == "all" or t.kind == kind)
            and (category == "all" or t.category == category)
            and (not needle or needle in " ".join((t.description, t.category, t.note, t.date)).casefold())
        ]
        if sort == "newest":
            return sorted(matches, key=lambda t: (t.date, t.id), reverse=True)
        if sort == "oldest":
            return sorted(matches, key=lambda t: (t.date, t.id))
        if sort == "highest":
            return sorted(matches, key=lambda t: (-t.amount, t.date, t.id))
        if sort == "lowest":
            return sorted(matches, key=lambda t: (t.amount, t.date, t.id))
        if sort == "category":
            return sorted(matches, key=lambda t: (t.category.casefold(), t.date, t.id))
        return sorted(matches, key=lambda t: (t.description.casefold(), t.date, t.id))

    def available_months(self) -> list[str]:
        months = {t.date[:7] for t in self._transactions.values()}
        months.update(month for month, _ in self._budgets)
        return sorted(months, reverse=True)

    def preferred_month(self) -> str:
        months = self.available_months()
        return months[0] if months else date.today().strftime("%Y-%m")

    def set_budget(self, month: str, category: str, amount: str | Decimal) -> Decimal:
        validate_month(month)
        if category not in EXPENSE_CATEGORIES:
            raise ValidationError("Budgets can only be set for expense categories.")
        parsed = parse_money(amount)
        updated = self._budgets.copy()
        updated[(month, category)] = parsed
        self._commit(self._transactions, updated)
        return parsed

    def remove_budget(self, month: str, category: str) -> None:
        validate_month(month)
        if (month, category) not in self._budgets:
            raise ValidationError("No budget exists for that month and category.")
        updated = self._budgets.copy()
        del updated[(month, category)]
        self._commit(self._transactions, updated)

    def get_budgets(self, month: str) -> dict[str, Decimal]:
        validate_month(month)
        return {category: amount for (m, category), amount in self._budgets.items() if m == month}

    def summarize(self, month: str) -> dict:
        """O(n) grouped monthly totals + monthly budget usage per category."""
        validate_month(month)
        income, expense, count = ZERO, ZERO, 0
        spending = {category: ZERO for category in EXPENSE_CATEGORIES}
        for t in self._transactions.values():
            if not t.date.startswith(month + "-"):
                continue
            count += 1
            if t.kind == "income":
                income += t.amount
            else:
                expense += t.amount
                spending[t.category] += t.amount
        budgets = self.get_budgets(month)
        budget_rows = [
            {
                "category": category, "limit": limit,
                "spent": spending[category], "remaining": limit - spending[category],
                "percent": (spending[category] / limit * 100),
                "over": spending[category] > limit,
            }
            for category, limit in sorted(budgets.items())
        ]
        nonzero = {category: total for category, total in spending.items() if total > ZERO}
        return {
            "month": month, "income": income, "expenses": expense,
            "balance": income - expense, "count": count,
            "spending_by_category": dict(sorted(nonzero.items(), key=lambda item: (-item[1], item[0]))),
            "budgets": budget_rows,
            "total_budget": sum(budgets.values(), ZERO),
            "budgeted_spending": sum((spending[c] for c in budgets), ZERO),
            "unbudgeted_spending": sum((v for c, v in spending.items() if c not in budgets), ZERO),
        }

    def export_csv(
        self, destination: str | Path, *, month: str | None = None,
        kind: str = "all", category: str = "all", search: str = "",
        sort: str = "newest",
    ) -> int:
        """Export exactly the currently requested subset with proper CSV escaping."""
        rows = self.list_transactions(
            month=month, kind=kind, category=category, search=search, sort=sort,
        )
        destination = Path(destination)
        if destination.resolve() == self.path.resolve():
            raise ValidationError("CSV destination cannot overwrite your JSON database.")
        try:
            with destination.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("ID", "Date", "Type", "Category", "Description", "Amount", "Note"))
                for t in rows:
                    writer.writerow((t.id, t.date, t.kind, t.category, t.description, money_text(t.amount), t.note))
        except OSError as exc:
            raise OSError(f"Unable to export CSV: {exc}") from exc
        return len(rows)
