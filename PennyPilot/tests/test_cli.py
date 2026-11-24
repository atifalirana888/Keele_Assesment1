"""CLI integration checks via real subprocesses.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
The student must review, understand and acknowledge this use in their submission.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from pennypilot.service import FinanceService

ROOT = Path(__file__).resolve().parent.parent


class CLITests(unittest.TestCase):
    def run_cli(self, input_text: str, path: Path):
        return subprocess.run(
            [sys.executable, str(ROOT / "cli.py"), "--data", str(path)],
            input=input_text, text=True, capture_output=True, timeout=15, cwd=ROOT,
        )

    def test_42_cli_exits_cleanly(self):
        with TemporaryDirectory() as folder:
            result = self.run_cli("0\n", Path(folder) / "ledger.json")
        self.assertEqual(result.returncode, 0)
        self.assertIn("PENNYPILOT", result.stdout.replace(" ", ""))
        self.assertIn("Goodbye", result.stdout)

    def test_43_cli_can_add_and_show_dashboard(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "ledger.json"
            # 3 add: expense, date, category (Enter -> default), description, amount, note.
            result = self.run_cli("3\nexpense\n2026-11-03\n\nCoffee beans\n12.35\n\n1\n2026-11\n0\n", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(path.exists())
            self.assertIn("Coffee beans", result.stdout)
            self.assertIn("£12.35", result.stdout)

    def test_44_cli_invalid_amount_survives(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "ledger.json"
            result = self.run_cli("3\nexpense\n2026-11-03\n\nCoffee beans\n0\n\n0\n", path)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Amount must be greater than 0", result.stdout)

    def test_45_cli_invalid_menu_survives(self):
        with TemporaryDirectory() as folder:
            result = self.run_cli("99\n0\n", Path(folder) / "ledger.json")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Please choose a number from 0 to 9", result.stdout)

    def test_55_cli_editor_can_clear_an_existing_note(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "ledger.json"
            service = FinanceService(path)
            item = service.add_transaction(
                date="2026-11-20", kind="expense", category="Groceries",
                description="Old transaction", amount="2.00", note="old note",
            )
            user_input = "4\n" + item.id + "\n" + "\n" * 5 + "/clear\n0\n"
            result = self.run_cli(user_input, path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(FinanceService(path).get_transaction(item.id).note, "")


if __name__ == "__main__":
    unittest.main()
