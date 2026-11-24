"""GUI smoke checks. Tkinter display tests skip when no graphical display exists.

GenAI acknowledgement: This file was created with assistance from OpenAI ChatGPT.
The student must review, understand and acknowledge this use in their submission.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import ttk
import unittest

from gui import PennyPilotApp
from pennypilot.service import FinanceService


class GUISmokeTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.service = FinanceService(Path(self.folder.name) / "records.json")
        try:
            self.window = PennyPilotApp(self.service)
        except tk.TclError as exc:
            self.skipTest(f"No display for Tkinter: {exc}")
        self.addCleanup(self.window.destroy)

    @staticmethod
    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from GUISmokeTests.descendants(child)

    def editor_controls(self):
        editor = next(w for w in self.window.winfo_children() if isinstance(w, tk.Toplevel))
        entries = [w for w in self.descendants(editor) if type(w) is tk.Entry]
        buttons = [w for w in self.descendants(editor) if isinstance(w, tk.Button)]
        return editor, entries, buttons

    def test_46_all_pages_draw_without_errors(self):
        for page in ("overview", "transactions", "budgets", "about"):
            with self.subTest(page=page):
                self.window.show_page(page)
                self.window.update_idletasks()

    def test_47_transaction_all_months_filter(self):
        self.window.month_var.set("*")
        self.window.show_page("transactions")
        self.assertIsNone(self.window._filters()["month"])
        self.window.show_page("overview")
        self.assertNotEqual(self.window.month_var.get(), "*")

    def test_48_gui_uses_same_service_record(self):
        self.service.add_transaction(
            date="2026-11-01", kind="expense", category="Groceries",
            description="Grocery test", amount="11.11",
        )
        self.window.month_var.set("2026-11")
        self.window.show_page("transactions")
        self.assertEqual(len(self.window.tree.get_children()), 1)

    def test_49_gui_add_dialog_saves_a_transaction(self):
        self.window.open_transaction_editor()
        editor, entries, buttons = self.editor_controls()
        self.assertEqual(len(entries), 3)
        for entry, value in zip(entries, ("2026-11-20", "Lunch from GUI", "19.55")):
            entry.delete(0, "end")
            entry.insert(0, value)
        next(button for button in buttons if button.cget("text") == "Save transaction").invoke()
        self.assertFalse(editor.winfo_exists())
        self.assertEqual(self.service.list_transactions()[0].description, "Lunch from GUI")

    def test_50_gui_edit_can_clear_note(self):
        item = self.service.add_transaction(
            date="2026-11-20", kind="expense", category="Groceries",
            description="Lunch from GUI", amount="19", note="old note",
        )
        self.window.open_transaction_editor(item.id)
        editor, entries, buttons = self.editor_controls()
        note = next(w for w in self.descendants(editor) if isinstance(w, tk.Text))
        note.delete("1.0", "end")
        next(button for button in buttons if button.cget("text") == "Save changes").invoke()
        self.assertEqual(self.service.get_transaction(item.id).note, "")

    def test_51_gui_budget_editor_saves_limit(self):
        self.window.month_var.set("2026-11")
        self.window.open_budget_editor("Groceries")
        editor, entries, buttons = self.editor_controls()
        self.assertEqual(len(entries), 1)
        entries[0].insert(0, "240")
        next(button for button in buttons if button.cget("text") == "Save budget").invoke()
        self.assertEqual(str(self.service.get_budgets("2026-11")["Groceries"]), "240.00")

    def test_52_gui_delete_selected_uses_confirmation(self):
        item = self.service.add_transaction(
            date="2026-11-20", kind="expense", category="Groceries",
            description="Delete from GUI", amount="12.20",
        )
        self.window.month_var.set("2026-11")
        self.window.show_page("transactions")
        self.window.tree.selection_set(item.id)
        with patch("gui.messagebox.askyesno", return_value=True):
            self.window._delete_selected()
        self.assertEqual(len(self.service.list_transactions()), 0)

    def test_53_gui_filtered_csv_export(self):
        item = self.service.add_transaction(
            date="2026-11-20", kind="expense", category="Groceries",
            description="Export from GUI", amount="15.25",
        )
        self.window.month_var.set("2026-11")
        self.window.show_page("transactions")
        destination = Path(self.folder.name) / "gui_export.csv"
        with patch("gui.filedialog.asksaveasfilename", return_value=str(destination)), \
             patch("gui.messagebox.showinfo"):
            self.window._export_csv()
        self.assertTrue(destination.exists())
        self.assertIn("Export from GUI", destination.read_text(encoding="utf-8-sig"))

    def test_54_gui_invalid_form_does_not_save(self):
        self.window.open_transaction_editor()
        editor, entries, buttons = self.editor_controls()
        for entry, value in zip(entries, ("2026-11-20", "Invalid amount", "0")):
            entry.delete(0, "end")
            entry.insert(0, value)
        with patch("gui.messagebox.showwarning") as warning:
            next(button for button in buttons if button.cget("text") == "Save transaction").invoke()
        self.assertTrue(warning.called)
        self.assertTrue(editor.winfo_exists())
        self.assertEqual(self.service.list_transactions(), [])
        editor.destroy()


if __name__ == "__main__":
    unittest.main()
