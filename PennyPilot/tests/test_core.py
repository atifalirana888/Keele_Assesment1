"""Automated normal, boundary, invalid and persistence test cases.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
The student must review, understand and acknowledge this use in their submission.
"""

from __future__ import annotations

import csv
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pennypilot.models import (
    Transaction, ValidationError, money_display, parse_money, validate_date, validate_month,
)
from pennypilot.service import FinanceService
from pennypilot.storage import DataFileError


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data" / "records.json"
        self.service = FinanceService(self.path)

    def add(self, date="2026-11-01", kind="expense", category="Groceries",
            description="Food shop", amount="20.50", note=""):
        return self.service.add_transaction(
            date=date, kind=kind, category=category,
            description=description, amount=amount, note=note,
        )

    def test_01_starts_empty_without_creating_file(self):
        self.assertFalse(self.path.exists())
        self.assertEqual(self.service.list_transactions(), [])
        self.assertEqual(self.service.summarize("2026-11")["balance"], Decimal("0.00"))

    def test_02_add_creates_json_and_uses_exact_amount(self):
        transaction = self.add(amount="0.10")
        self.assertEqual(transaction.amount, Decimal("0.10"))
        self.assertEqual(self.service.get_transaction(transaction.id).description, "Food shop")
        self.assertTrue(self.path.exists())
        self.assertEqual(json.loads(self.path.read_text())["schema_version"], 1)

    def test_03_reopens_saved_records(self):
        transaction = self.add()
        loaded = FinanceService(self.path)
        self.assertEqual(loaded.get_transaction(transaction.id), transaction)

    def test_04_edit_preserves_id_and_persists(self):
        before = self.add()
        after = self.service.edit_transaction(before.id, description="Edited shop", amount="99.20", note="New note")
        self.assertEqual(after.id, before.id)
        self.assertEqual(after.amount, Decimal("99.20"))
        self.assertEqual(FinanceService(self.path).get_transaction(before.id).note, "New note")

    def test_05_edit_change_type_and_category(self):
        before = self.add()
        after = self.service.edit_transaction(before.id, kind="income", category="Gift", amount="60")
        self.assertEqual(after.kind, "income")
        self.assertEqual(after.category, "Gift")

    def test_06_edit_rejects_incompatible_category_without_change(self):
        before = self.add()
        with self.assertRaises(ValidationError):
            self.service.edit_transaction(before.id, kind="income")
        self.assertEqual(self.service.get_transaction(before.id), before)

    def test_07_delete_removes_from_disk(self):
        item = self.add()
        self.service.delete_transaction(item.id)
        self.assertEqual(FinanceService(self.path).list_transactions(), [])

    def test_08_missing_id_raises_readable_error(self):
        with self.assertRaisesRegex(ValidationError, "not found"):
            self.service.delete_transaction("missing-id")

    def test_09_search_matches_description_case_insensitively(self):
        self.add(description="Coffee Shop")
        self.add(description="Taxi Ride", category="Transport")
        matches = self.service.list_transactions(search="cOfFeE")
        self.assertEqual([t.description for t in matches], ["Coffee Shop"])

    def test_10_search_note_and_category(self):
        self.add(note="Receipt, special lunch")
        self.assertEqual(len(self.service.list_transactions(search="special")), 1)
        self.assertEqual(len(self.service.list_transactions(search="GROCERIES")), 1)

    def test_11_month_filter_and_all_months(self):
        self.add(date="2026-10-31")
        self.add(date="2026-11-01")
        self.assertEqual(len(self.service.list_transactions(month="2026-10")), 1)
        self.assertEqual(len(self.service.list_transactions(month=None)), 2)

    def test_12_kind_category_filters_can_combine(self):
        self.add()
        self.add(kind="income", category="Salary", amount="2500")
        self.assertEqual(len(self.service.list_transactions(kind="expense", category="Groceries")), 1)
        self.assertEqual(len(self.service.list_transactions(kind="income", category="Groceries")), 0)

    def test_13_sort_orders_dates(self):
        self.add(date="2026-11-02", description="Second")
        self.add(date="2026-11-01", description="First")
        self.assertEqual([t.description for t in self.service.list_transactions(sort="newest")], ["Second", "First"])
        self.assertEqual([t.description for t in self.service.list_transactions(sort="oldest")], ["First", "Second"])

    def test_14_sort_orders_amount_and_description(self):
        self.add(description="Apple", amount="3")
        self.add(description="Banana", amount="21")
        self.assertEqual(self.service.list_transactions(sort="highest")[0].description, "Banana")
        self.assertEqual(self.service.list_transactions(sort="lowest")[0].description, "Apple")
        self.assertEqual(self.service.list_transactions(sort="description")[0].description, "Apple")

    def test_15_invalid_filters_rejected(self):
        for filter_kwargs in ({"kind": "oops"}, {"category": "Not a category"},
                              {"sort": "random"}, {"month": "2026-13"}):
            with self.subTest(filter_kwargs=filter_kwargs), self.assertRaises(ValidationError):
                self.service.list_transactions(**filter_kwargs)

    def test_16_monthly_income_expense_and_balance(self):
        self.add(amount="20.55")
        self.add(amount="0.10")
        self.add(kind="income", category="Salary", amount="100.00")
        self.add(date="2026-10-01", amount="90")
        summary = self.service.summarize("2026-11")
        self.assertEqual(summary["income"], Decimal("100.00"))
        self.assertEqual(summary["expenses"], Decimal("20.65"))
        self.assertEqual(summary["balance"], Decimal("79.35"))
        self.assertEqual(summary["count"], 3)

    def test_17_category_grouping_is_amount_sorted(self):
        self.add(category="Groceries", amount="12")
        self.add(category="Transport", amount="40")
        self.add(category="Groceries", amount="9")
        grouped = self.service.summarize("2026-11")["spending_by_category"]
        self.assertEqual(list(grouped), ["Transport", "Groceries"])
        self.assertEqual(grouped["Groceries"], Decimal("21.00"))

    def test_18_budget_create_update_and_reload(self):
        self.service.set_budget("2026-11", "Groceries", "200")
        self.service.set_budget("2026-11", "Groceries", "350.50")
        self.assertEqual(FinanceService(self.path).get_budgets("2026-11")["Groceries"], Decimal("350.50"))

    def test_19_budget_over_limit(self):
        self.add(amount="80")
        self.service.set_budget("2026-11", "Groceries", "50")
        budget = self.service.summarize("2026-11")["budgets"][0]
        self.assertTrue(budget["over"])
        self.assertEqual(budget["remaining"], Decimal("-30.00"))
        self.assertEqual(budget["percent"], Decimal("160"))

    def test_20_budget_exact_limit_is_not_over(self):
        self.add(amount="50")
        self.service.set_budget("2026-11", "Groceries", "50")
        self.assertFalse(self.service.summarize("2026-11")["budgets"][0]["over"])

    def test_21_budgets_are_specific_to_month(self):
        self.service.set_budget("2026-11", "Groceries", "60")
        self.assertEqual(self.service.get_budgets("2026-10"), {})

    def test_22_unbudgeted_spending(self):
        self.add(category="Groceries", amount="10")
        self.add(category="Transport", amount="15")
        self.service.set_budget("2026-11", "Groceries", "50")
        summary = self.service.summarize("2026-11")
        self.assertEqual(summary["budgeted_spending"], Decimal("10"))
        self.assertEqual(summary["unbudgeted_spending"], Decimal("15"))

    def test_23_remove_budget_keeps_transaction(self):
        self.add()
        self.service.set_budget("2026-11", "Groceries", "50")
        self.service.remove_budget("2026-11", "Groceries")
        self.assertEqual(self.service.get_budgets("2026-11"), {})
        self.assertEqual(len(self.service.list_transactions()), 1)

    def test_24_bad_budget_category_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.set_budget("2026-11", "Salary", "100")

    def test_25_remove_missing_budget_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.remove_budget("2026-11", "Groceries")

    def test_26_csv_filter_and_escaping(self):
        self.add(description='Food, "weekend"', note='Use, "coupon"')
        self.add(date="2026-10-01", description="Other month")
        out = Path(self.temp.name) / "export.csv"
        count = self.service.export_csv(out, month="2026-11")
        with out.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["Description"], 'Food, "weekend"')
        self.assertEqual(rows[0]["Note"], 'Use, "coupon"')
        self.assertEqual(rows[0]["Amount"], "20.50")

    def test_27_empty_csv_has_header(self):
        out = Path(self.temp.name) / "empty.csv"
        self.assertEqual(self.service.export_csv(out), 0)
        with out.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 1)
        self.assertIn("Amount", rows[0])

    def test_csv_cannot_overwrite_database(self):
        self.add()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValidationError, "overwrite"):
            self.service.export_csv(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_28_failed_save_does_not_change_memory(self):
        self.add()
        before = self.service.list_transactions()
        with patch("pennypilot.service.save_data", side_effect=DataFileError("disk full")):
            with self.assertRaises(DataFileError):
                self.add(description="Second")
        self.assertEqual(before, self.service.list_transactions())

    def test_29_corrupted_file_error(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(DataFileError):
            FinanceService(self.path)

    def test_30_wrong_schema_error(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('{"schema_version": 3, "transactions": [], "budgets": []}')
        with self.assertRaisesRegex(DataFileError, "schema"):
            FinanceService(self.path)

    def test_31_duplicate_record_id_error(self):
        t = self.add()
        payload = json.loads(self.path.read_text())
        payload["transactions"].append(t.to_dict())
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(DataFileError, "Duplicate"):
            FinanceService(self.path)

    def test_32_duplicate_budget_error(self):
        self.service.set_budget("2026-11", "Groceries", "100")
        payload = json.loads(self.path.read_text())
        payload["budgets"].append(payload["budgets"][0])
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(DataFileError, "Duplicate"):
            FinanceService(self.path)

    def test_33_bad_record_does_not_partially_load(self):
        first = self.add()
        payload = json.loads(self.path.read_text())
        payload["transactions"].append({"id": "bad-id"})
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(DataFileError):
            FinanceService(self.path)
        self.assertEqual(self.service.get_transaction(first.id), first)

    def test_34_preferred_month_and_available_months(self):
        self.add(date="2026-09-02")
        self.add(date="2026-11-01")
        self.service.set_budget("2026-10", "Housing", "1000")
        self.assertEqual(self.service.available_months(), ["2026-11", "2026-10", "2026-09"])
        self.assertEqual(self.service.preferred_month(), "2026-11")


class ValidationTests(unittest.TestCase):
    def test_35_leap_day_and_invalid_day(self):
        self.assertEqual(validate_date("2024-02-29"), "2024-02-29")
        for value in ("2026-02-29", "2026-04-31", "2026/11/20", "2026-1-02"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_date(value)

    def test_36_month_range(self):
        for value in ("2026-00", "2026-13", "199-11", "2201-01", "2026-1"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_month(value)

    def test_37_invalid_amounts(self):
        for value in ("0", "-1", "2.345", "1e3", "£4", "NaN", "1000000000", "", "  ", 0.1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_money(value)

    def test_38_amount_boundary(self):
        self.assertEqual(parse_money("0.01"), Decimal("0.01"))
        self.assertEqual(parse_money("999999999.99"), Decimal("999999999.99"))

    def test_39_invalid_description_and_notes(self):
        base = {"id": "valid123", "date": "2026-11-02", "kind": "expense",
                "category": "Groceries", "amount": "10", "description": "Valid"}
        for fields in ({"description": "X"}, {"description": "y" * 71}, {"note": "x" * 241}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                Transaction.create(**(base | fields))

    def test_40_invalid_category_or_kind(self):
        base = {"id": "valid123", "date": "2026-11-02", "kind": "expense",
                "category": "Groceries", "amount": "10", "description": "Valid"}
        for fields in ({"kind": "refund"}, {"kind": "income"}, {"category": "Space travel"}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                Transaction.create(**(base | fields))

    def test_41_money_formatting(self):
        self.assertEqual(money_display(Decimal("-1020.5")), "−£1,020.50")
        self.assertEqual(money_display(Decimal("10.00")), "£10.00")


if __name__ == "__main__":
    unittest.main()
