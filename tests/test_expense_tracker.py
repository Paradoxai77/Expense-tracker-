"""
Unit tests for the Expense Tracker application.
Uses standard library unittest.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

import expense_tracker


class TestExpenseTracker(unittest.TestCase):
    """Test suite covering core features, bonus features, and edge cases."""

    def setUp(self):
        """Create a temporary file for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = os.path.join(self.temp_dir.name, "test_expenses.json")

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def run_cli(self, args):
        """Helper to run the CLI with a custom data file and captured stdout/stderr."""
        full_args = ["--data-file", self.data_file] + args
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with patch("sys.stdout", stdout_capture), patch("sys.stderr", stderr_capture):
            exit_code = expense_tracker.main(full_args)

        return exit_code, stdout_capture.getvalue(), stderr_capture.getvalue()

    # -----------------------------------------------------------------------
    # Core Command Tests: Add
    # -----------------------------------------------------------------------

    def test_add_basic(self):
        """Test adding a basic expense."""
        code, out, err = self.run_cli(["add", "--description", "Lunch", "--amount", "20"])
        self.assertEqual(code, 0)
        self.assertIn("Expense added successfully (ID: 1)", out)

        data = expense_tracker.load_data(self.data_file)
        self.assertEqual(len(data["expenses"]), 1)
        exp = data["expenses"][0]
        self.assertEqual(exp["id"], 1)
        self.assertEqual(exp["description"], "Lunch")
        self.assertEqual(exp["amount"], 20.0)
        self.assertEqual(exp["category"], "General")
        self.assertEqual(exp["date"], date.today().isoformat())
        self.assertEqual(data["next_id"], 2)

    def test_add_with_category_and_float_amount(self):
        """Test adding expense with specific category and decimal amount."""
        code, out, err = self.run_cli(["add", "--description", "Coffee", "--amount", "4.50", "--category", "Food"])
        self.assertEqual(code, 0)
        self.assertIn("Expense added successfully (ID: 1)", out)

        data = expense_tracker.load_data(self.data_file)
        exp = data["expenses"][0]
        self.assertEqual(exp["category"], "Food")
        self.assertEqual(exp["amount"], 4.5)

    def test_add_multiple_auto_increment_ids(self):
        """Test that IDs auto-increment sequentially."""
        self.run_cli(["add", "--description", "Item 1", "--amount", "10"])
        code, out, err = self.run_cli(["add", "--description", "Item 2", "--amount", "15"])
        self.assertEqual(code, 0)
        self.assertIn("Expense added successfully (ID: 2)", out)

        data = expense_tracker.load_data(self.data_file)
        self.assertEqual(len(data["expenses"]), 2)
        self.assertEqual(data["expenses"][0]["id"], 1)
        self.assertEqual(data["expenses"][1]["id"], 2)
        self.assertEqual(data["next_id"], 3)

    # -----------------------------------------------------------------------
    # Core Command Tests: Update
    # -----------------------------------------------------------------------

    def test_update_description_and_amount(self):
        """Test updating both description and amount."""
        self.run_cli(["add", "--description", "Lunch", "--amount", "20"])
        code, out, err = self.run_cli(["update", "--id", "1", "--description", "Late lunch", "--amount", "25"])
        self.assertEqual(code, 0)
        self.assertIn("Expense updated successfully", out)

        data = expense_tracker.load_data(self.data_file)
        exp = data["expenses"][0]
        self.assertEqual(exp["description"], "Late lunch")
        self.assertEqual(exp["amount"], 25.0)

    def test_update_single_field(self):
        """Test updating description alone or amount alone."""
        self.run_cli(["add", "--description", "Lunch", "--amount", "20"])
        # Update description only
        code, out, err = self.run_cli(["update", "--id", "1", "--description", "Dinner"])
        self.assertEqual(code, 0)
        # Update amount only
        code, out, err = self.run_cli(["update", "--id", "1", "--amount", "30.50"])
        self.assertEqual(code, 0)

        data = expense_tracker.load_data(self.data_file)
        exp = data["expenses"][0]
        self.assertEqual(exp["description"], "Dinner")
        self.assertEqual(exp["amount"], 30.5)

    def test_update_category(self):
        """Test updating expense category."""
        self.run_cli(["add", "--description", "Lunch", "--amount", "20"])
        code, out, err = self.run_cli(["update", "--id", "1", "--category", "Dining"])
        self.assertEqual(code, 0)

        data = expense_tracker.load_data(self.data_file)
        self.assertEqual(data["expenses"][0]["category"], "Dining")

    # -----------------------------------------------------------------------
    # Core Command Tests: Delete
    # -----------------------------------------------------------------------

    def test_delete_success(self):
        """Test deleting an expense."""
        self.run_cli(["add", "--description", "Item 1", "--amount", "10"])
        self.run_cli(["add", "--description", "Item 2", "--amount", "20"])

        code, out, err = self.run_cli(["delete", "--id", "1"])
        self.assertEqual(code, 0)
        self.assertIn("Expense deleted successfully", out)

        data = expense_tracker.load_data(self.data_file)
        self.assertEqual(len(data["expenses"]), 1)
        self.assertEqual(data["expenses"][0]["id"], 2)

    def test_delete_id_never_reused(self):
        """Test that IDs are never reused after deletion."""
        self.run_cli(["add", "--description", "Item 1", "--amount", "10"])  # ID 1
        self.run_cli(["delete", "--id", "1"])
        code, out, err = self.run_cli(["add", "--description", "Item 2", "--amount", "20"])
        self.assertEqual(code, 0)
        self.assertIn("Expense added successfully (ID: 2)", out)

        data = expense_tracker.load_data(self.data_file)
        self.assertEqual(len(data["expenses"]), 1)
        self.assertEqual(data["expenses"][0]["id"], 2)
        self.assertEqual(data["next_id"], 3)

    # -----------------------------------------------------------------------
    # Core Command Tests: List
    # -----------------------------------------------------------------------

    def test_list_all_table_format(self):
        """Test listing expenses in aligned table format."""
        self.run_cli(["add", "--description", "Lunch", "--amount", "20", "--category", "Food"])
        self.run_cli(["add", "--description", "Dinner", "--amount", "10.5", "--category", "General"])

        code, out, err = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("ID", out)
        self.assertIn("Date", out)
        self.assertIn("Description", out)
        self.assertIn("Category", out)
        self.assertIn("Amount", out)
        self.assertIn("Lunch", out)
        self.assertIn("$20", out)
        self.assertIn("Dinner", out)
        self.assertIn("$10.50", out)

    def test_list_filter_category(self):
        """Test filtering list by category."""
        self.run_cli(["add", "--description", "Burger", "--amount", "15", "--category", "Food"])
        self.run_cli(["add", "--description", "Train", "--amount", "5", "--category", "Travel"])

        code, out, err = self.run_cli(["list", "--category", "Food"])
        self.assertEqual(code, 0)
        self.assertIn("Burger", out)
        self.assertNotIn("Train", out)

    def test_list_empty(self):
        """Test list when no expenses exist."""
        code, out, err = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("No expenses found.", out)

    # -----------------------------------------------------------------------
    # Core Command Tests: Summary
    # -----------------------------------------------------------------------

    def test_summary_total(self):
        """Test overall summary of all expenses."""
        self.run_cli(["add", "--description", "Lunch", "--amount", "20"])
        self.run_cli(["add", "--description", "Dinner", "--amount", "10"])

        code, out, err = self.run_cli(["summary"])
        self.assertEqual(code, 0)
        self.assertIn("Total expenses: $30", out)

    def test_summary_monthly_current_year(self):
        """Test monthly summary only counts current year expenses for the given month."""
        today = date.today()
        current_year = today.year

        # Seed data directly with different dates
        data = {
            "next_id": 4,
            "expenses": [
                # Expense in August of current year
                {"id": 1, "date": f"{current_year}-08-01", "description": "August Expense", "amount": 25.0, "category": "Food"},
                # Expense in August of previous year (should be excluded)
                {"id": 2, "date": f"{current_year - 1}-08-01", "description": "Old August Expense", "amount": 100.0, "category": "Food"},
                # Expense in another month of current year (should be excluded)
                {"id": 3, "date": f"{current_year}-09-01", "description": "September Expense", "amount": 40.0, "category": "Other"}
            ],
            "budgets": {}
        }
        expense_tracker.save_data(data, self.data_file)

        code, out, err = self.run_cli(["summary", "--month", "8"])
        self.assertEqual(code, 0)
        self.assertIn("Total expenses for August: $25", out)

    # -----------------------------------------------------------------------
    # Bonus Features: Budgets & CSV Export
    # -----------------------------------------------------------------------

    def test_budget_setting(self):
        """Test setting a monthly budget."""
        code, out, err = self.run_cli(["budget", "--month", "8", "--amount", "500"])
        self.assertEqual(code, 0)
        self.assertIn("Budget for August set to $500", out)

        data = expense_tracker.load_data(self.data_file)
        self.assertEqual(data["budgets"]["8"], 500.0)

    def test_budget_warning_on_exceed(self):
        """Test warning when adding an expense pushes total over budget."""
        current_month = date.today().month
        self.run_cli(["budget", "--month", str(current_month), "--amount", "50"])

        # First expense within budget
        code1, out1, _ = self.run_cli(["add", "--description", "Groceries", "--amount", "30"])
        self.assertEqual(code1, 0)
        self.assertNotIn("Warning:", out1)

        # Second expense pushes it over budget (30 + 25 = 55 > 50)
        code2, out2, _ = self.run_cli(["add", "--description", "Snacks", "--amount", "25"])
        self.assertEqual(code2, 0)
        self.assertIn("Expense added successfully (ID: 2)", out2)
        self.assertIn("Warning: Monthly expenses for", out2)
        self.assertIn("exceeded your budget", out2)

    def test_csv_export(self):
        """Test exporting expenses to a CSV file."""
        self.run_cli(["add", "--description", "Lunch", "--amount", "20", "--category", "Food"])
        self.run_cli(["add", "--description", "Taxi", "--amount", "15.75", "--category", "Travel"])

        csv_path = os.path.join(self.temp_dir.name, "exported.csv")
        code, out, err = self.run_cli(["export", "--file", csv_path])
        self.assertEqual(code, 0)
        self.assertIn("Expenses exported successfully", out)

        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]

        self.assertEqual(lines[0], "ID,Date,Description,Category,Amount")
        self.assertIn("Lunch", lines[1])
        self.assertIn("Food", lines[1])
        self.assertIn("20.0", lines[1])
        self.assertIn("Taxi", lines[2])
        self.assertIn("Travel", lines[2])
        self.assertIn("15.75", lines[2])

    # -----------------------------------------------------------------------
    # Edge Cases & Error Handling
    # -----------------------------------------------------------------------

    def test_add_empty_description_error(self):
        """Test error when description is empty or only whitespace."""
        code, out, err = self.run_cli(["add", "--description", "   ", "--amount", "20"])
        self.assertNotEqual(code, 0)
        self.assertIn("Error: Description cannot be empty.", err)

    def test_add_negative_and_zero_amount_error(self):
        """Test error when amount is zero or negative."""
        code, _, err = self.run_cli(["add", "--description", "Test", "--amount", "0"])
        self.assertNotEqual(code, 0)
        self.assertIn("Amount must be a positive number", err)

        code, _, err = self.run_cli(["add", "--description", "Test", "--amount", "-15"])
        self.assertNotEqual(code, 0)
        self.assertIn("Amount must be a positive number", err)

    def test_add_non_numeric_amount_error(self):
        """Test error when amount is non-numeric."""
        code, _, err = self.run_cli(["add", "--description", "Test", "--amount", "not_a_number"])
        self.assertNotEqual(code, 0)
        self.assertIn("Amount must be a valid number", err)

    def test_update_non_existent_id(self):
        """Test updating an ID that does not exist."""
        code, _, err = self.run_cli(["update", "--id", "999", "--amount", "50"])
        self.assertNotEqual(code, 0)
        self.assertIn("Expense with ID 999 not found.", err)

    def test_update_missing_all_fields(self):
        """Test updating with neither description, amount, nor category."""
        self.run_cli(["add", "--description", "Lunch", "--amount", "20"])
        code, _, err = self.run_cli(["update", "--id", "1"])
        self.assertNotEqual(code, 0)
        self.assertIn("At least one of --description, --amount, or --category must be provided to update.", err)

    def test_delete_non_existent_id(self):
        """Test deleting an ID that does not exist."""
        code, _, err = self.run_cli(["delete", "--id", "999"])
        self.assertNotEqual(code, 0)
        self.assertIn("Expense with ID 999 not found.", err)

    def test_invalid_month_range(self):
        """Test summary and budget with months outside 1-12 or invalid."""
        for invalid_m in ["0", "13", "-1", "abc"]:
            code, _, err = self.run_cli(["summary", "--month", invalid_m])
            self.assertNotEqual(code, 0)
            self.assertIn("Month must be an integer between 1 and 12", err)

            code, _, err = self.run_cli(["budget", "--month", invalid_m, "--amount", "100"])
            self.assertNotEqual(code, 0)
            self.assertIn("Month must be an integer between 1 and 12", err)

    def test_empty_json_file(self):
        """Test friendly error when data file is 0 bytes."""
        with open(self.data_file, "w") as f:
            pass  # create empty file

        code, _, err = self.run_cli(["list"])
        self.assertNotEqual(code, 0)
        self.assertIn("is empty. Please check or reset the file.", err)

    def test_corrupted_json_file(self):
        """Test friendly error when data file has malformed JSON."""
        with open(self.data_file, "w") as f:
            f.write("{invalid json content!;;")

        code, _, err = self.run_cli(["list"])
        self.assertNotEqual(code, 0)
        self.assertIn("is corrupted or contains invalid JSON", err)

    def test_missing_required_arguments(self):
        """Test that missing required arguments output clear error."""
        code, _, err = self.run_cli(["add", "--amount", "20"])
        self.assertNotEqual(code, 0)
        self.assertIn("the following arguments are required: --description", err)


if __name__ == "__main__":
    unittest.main()

