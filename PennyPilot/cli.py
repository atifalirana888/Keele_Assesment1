"""PennyPilot — the shared finance service.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pennypilot.bootstrap import add_data_arguments, open_service
from pennypilot.models import (
    EXPENSE_CATEGORIES, ValidationError, categories_for, money_display,
    validate_month,
)
from pennypilot.service import FinanceService, SORT_OPTIONS
from pennypilot.storage import DataFileError

RULE = "─" * 85

def ask(prompt: str, default: str = "") -> str:
    """Use enter for default; callers handle validation errors explicitly."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else default

def ask_month(default: str) -> str:
    month = ask("Month (YYYY-MM)", default)
    validate_month(month)
    return month

def select_category(kind: str, current: str = "") -> str:
    options = categories_for(kind)
    print("Categories: " + "  |  ".join(options))
    return ask("Category", current if current in options else options[0])

def dashboard(service: FinanceService) -> None:
    month = ask_month(service.preferred_month())
    summary = service.summarize(month)
    print(f"\n  MONTHLY OVERVIEW   {month}\n{RULE}")
    print(f"  Income        {money_display(summary['income']):>18}")
    print(f"  Expenses      {money_display(summary['expenses']):>18}")
    print(f"  Net balance   {money_display(summary['balance']):>18}")
    print(f"  Entries       {summary['count']:>18}")
    print("\n  Spending by category:")
    if summary["spending_by_category"]:
        max_amount = max(summary["spending_by_category"].values())
        for category, amount in summary["spending_by_category"].items():
            bars = "█" * max(1, round(amount / max_amount * 22))
            print(f"  {category:<17} {money_display(amount):>14}  {bars}")
    else:
        print("  Nothing recorded yet for this month.")
    if summary["budgets"]:
        print("\n  Budget progress:")
        for item in summary["budgets"]:
            flag = "OVER BUDGET" if item["over"] else "on track"
            print(f"  {item['category']:<17} {money_display(item['spent'])} / "
                  f"{money_display(item['limit'])}  ({item['percent']:.0f}%) — {flag}")
    print(RULE)

def prompt_filters(default_month: str | None = None) -> dict:
    print("\n  FILTERS  (enter for the default; '*' for all months)")
    raw_month = ask("Month YYYY-MM or *", default_month or "*")
    month = None if raw_month == "*" else validate_month(raw_month)
    kind = ask("Type (all/income/expense)", "all").lower()
    category = ask("Category (all or exact category name)", "all")
    search = ask("Search description, note, date, category", "")
    print("Sort options: " + ", ".join(SORT_OPTIONS))
    sort = ask("Sort", "newest").lower()
    return {"month": month, "kind": kind, "category": category,
            "search": search, "sort": sort}

def print_transactions(service: FinanceService, filters: dict) -> None:
    transactions = service.list_transactions(**filters)
    print(f"\n  TRANSACTIONS — {len(transactions)} match(es)\n{RULE}")
    print(f"  {'Date':10}  {'Type':7}  {'Category':16}  {'Description':25} {'Amount':>14}")
    print(RULE)
    for t in transactions:
        desc = t.description if len(t.description) <= 25 else t.description[:22] + "..."
        print(f"  {t.date:10}  {t.kind:7}  {t.category[:16]:16}  {desc:25} "
              f"{money_display(t.amount):>14}")
        print(f"      ID: {t.id}" + (f"   Note: {t.note}" if t.note else ""))
    if not transactions:
        print("  No results. Try adjusting the filters or add a transaction.")
    print(RULE)

def add_transaction(service: FinanceService) -> None:
    print("\n  ADD TRANSACTION")
    kind = ask("Type (income/expense)", "expense").lower()
    if kind not in ("income", "expense"):
        raise ValidationError("Type must be income or expense.")
    fields = {
        "date": ask("Date YYYY-MM-DD", date.today().isoformat()),
        "kind": kind,
        "category": select_category(kind),
        "description": ask("Description"),
        "amount": ask("Amount (e.g. 12.50)"),
        "note": ask("Note (optional)"),
    }
    t = service.add_transaction(**fields)
    print(f"✓ Added {t.description} ({money_display(t.amount)}), ID: {t.id}")

def select_transaction(service: FinanceService) -> str:
    """Show recent entries to make choosing the stable ID straightforward."""
    recent = service.list_transactions()[:12]
    print("\n  Recent entries (copy an ID to select):")
    for t in recent:
        print(f"    {t.id}  {t.date}  {t.description[:28]:28}  {money_display(t.amount)}")
    return ask("Transaction ID")

def edit_transaction(service: FinanceService) -> None:
    transaction_id = select_transaction(service)
    t = service.get_transaction(transaction_id)
    print(f"\n  EDIT {t.description} — leave a value blank to keep it")
    kind = ask("Type (income/expense)", t.kind).lower()
    if kind not in ("income", "expense"):
        raise ValidationError("Type must be income or expense.")
    updated = {
        "date": ask("Date YYYY-MM-DD", t.date),
        "kind": kind,
        "category": select_category(kind, t.category),
        "description": ask("Description", t.description),
        "amount": ask("Amount", str(t.amount)),
        "note": t.note,
    }
    note_change = input("Note (Enter = keep, /clear = remove, or type replacement): ").strip()
    if note_change:
        updated["note"] = "" if note_change == "/clear" else note_change
    result = service.edit_transaction(transaction_id, **updated)
    print(f"✓ Updated {result.description} ({money_display(result.amount)})")


def delete_transaction(service: FinanceService) -> None:
    transaction_id = select_transaction(service)
    t = service.get_transaction(transaction_id)
    confirmed = ask(f"Delete '{t.description}' worth {money_display(t.amount)}? (yes/no)", "no")
    if confirmed.casefold() == "yes":
        service.delete_transaction(transaction_id)
        print("✓ Transaction deleted.")
    else:
        print("Deletion cancelled.")


def view_budgets(service: FinanceService) -> None:
    month = ask_month(service.preferred_month())
    summary = service.summarize(month)
    print(f"\n  BUDGETS FOR {month}\n{RULE}")
    print(f"  {'Category':20} {'Limit':>15} {'Spent':>15} {'Left':>15}   Status")
    for b in summary["budgets"]:
        print(f"  {b['category']:20} {money_display(b['limit']):>15} "
              f"{money_display(b['spent']):>15} {money_display(b['remaining']):>15}   "
              f"{'OVER' if b['over'] else 'On track'}")
    if not summary["budgets"]:
        print("  No budgets for this month. Use menu option 7 to create one.")
    print(f"  Unbudgeted spending: {money_display(summary['unbudgeted_spending'])}")
    print(RULE)


def set_budget(service: FinanceService) -> None:
    month = ask_month(service.preferred_month())
    category = select_category("expense")
    existing = service.get_budgets(month).get(category)
    amount = ask("Monthly limit", str(existing) if existing else "")
    value = service.set_budget(month, category, amount)
    print(f"✓ {month} {category} limit set to {money_display(value)}")


def remove_budget(service: FinanceService) -> None:
    month = ask_month(service.preferred_month())
    categories = service.get_budgets(month)
    if not categories:
        print("No budgets found for that month.")
        return
    print("Configured: " + ", ".join(categories))
    category = ask("Category to remove")
    service.remove_budget(month, category)
    print("✓ Budget removed (transactions are unchanged).")


def export_csv(service: FinanceService) -> None:
    filters = prompt_filters()
    path = ask("CSV file path", "transactions_export.csv")
    destination = Path(path).expanduser()
    if destination.exists() and ask("File already exists. Overwrite? (yes/no)", "no").lower() != "yes":
        print("Export cancelled.")
        return
    count = service.export_csv(destination, **filters)
    print(f"✓ Exported {count} entries to {destination.resolve()}")


ACTIONS = {
    "1": dashboard, "2": lambda service: print_transactions(service, prompt_filters()),
    "3": add_transaction, "4": edit_transaction, "5": delete_transaction,
    "6": view_budgets, "7": set_budget, "8": remove_budget, "9": export_csv,
}


def run(service: FinanceService) -> None:
    print("\n" + "═" * 85)
    print("  P E N N Y P I L O T  /  Personal finance, clearly organised")
    print("═" * 85)
    print(f"  Data: {service.path.resolve()}")
    while True:
        print("\n  1  Monthly dashboard       6  View monthly budgets")
        print("  2  Search / sort entries   7  Set or update budget")
        print("  3  Add transaction         8  Remove budget")
        print("  4  Edit transaction        9  Export filtered CSV")
        print("  5  Delete transaction      0  Exit")
        try:
            choice = ask("\nChoose an option")
            if choice == "0":
                print("Goodbye! Your changes have been saved automatically.")
                return
            if choice not in ACTIONS:
                print("Please choose a number from 0 to 9.")
                continue
            try:
                ACTIONS[choice](service)
            except (ValidationError, DataFileError, OSError) as exc:
                print(f"! {exc}")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting safely. Any completed changes were saved.")
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="PennyPilot command-line finance tracker")
    add_data_arguments(parser)
    args = parser.parse_args()
    try:
        service = open_service(args)
    except (DataFileError, OSError) as exc:
        parser.exit(1, f"Data file error: {exc}\n")
    run(service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
