#!/usr/bin/env python3
"""
Expense Tracker CLI Application
A lightweight, standard-library-only command-line expense tracker.
"""

import argparse
import calendar
import csv
import datetime
import json
import os
import sys
from typing import Any, Dict, List, Optional


class ExpenseTrackerError(Exception):
    """Custom exception for expected user or data errors."""
    pass


class CleanArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that outputs clean, single-line error messages without stack traces."""

    def error(self, message: str) -> None:
        sys.stderr.write(f"Error: {message}\n")
        sys.exit(2)


# ---------------------------------------------------------------------------
# Data Persistence Functions
# ---------------------------------------------------------------------------

DEFAULT_DATA_FILE = "expenses.json"


def get_default_data() -> Dict[str, Any]:
    """Returns the default blank schema for expenses data."""
    return {
        "next_id": 1,
        "expenses": [],
        "budgets": {}
    }


def load_data(filepath: str = DEFAULT_DATA_FILE) -> Dict[str, Any]:
    """
    Loads expense data from a JSON file.
    If the file does not exist, it initializes and returns a blank data structure.
    Raises ExpenseTrackerError if the file is empty or corrupted.
    """
    if not os.path.exists(filepath):
        return get_default_data()

    # Check for empty file
    if os.path.getsize(filepath) == 0:
        raise ExpenseTrackerError(
            f"Data file '{filepath}' is empty. Please check or reset the file."
        )

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ExpenseTrackerError(
            f"Data file '{filepath}' is corrupted or contains invalid JSON: {e}"
        )

    # Validate top-level schema
    if not isinstance(data, dict):
        raise ExpenseTrackerError(
            f"Data file '{filepath}' has invalid format (root must be a JSON object)."
        )

    if "expenses" not in data or not isinstance(data["expenses"], list):
        data["expenses"] = []
    if "next_id" not in data or not isinstance(data["next_id"], int):
        # Infer next_id if missing
        max_id = max((e.get("id", 0) for e in data["expenses"]), default=0)
        data["next_id"] = max_id + 1
    if "budgets" not in data or not isinstance(data["budgets"], dict):
        data["budgets"] = {}

    return data


def save_data(data: Dict[str, Any], filepath: str = DEFAULT_DATA_FILE) -> None:
    """Saves expense data to a JSON file atomically."""
    # Write to a temp file in the same directory, then rename to avoid corruption
    dir_name = os.path.dirname(filepath) or "."
    temp_file = os.path.join(dir_name, f".{os.path.basename(filepath)}.tmp")

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # On Windows, replace will overwrite existing file atomically
        os.replace(temp_file, filepath)
    except Exception as e:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise ExpenseTrackerError(f"Failed to save data to '{filepath}': {e}")


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def format_amount(amount: float) -> str:
    """
    Formats amounts consistently:
    e.g. $20 for whole numbers, $20.50 for decimals.
    """
    rounded = round(amount, 2)
    if rounded == int(rounded):
        return f"${int(rounded)}"
    return f"${rounded:.2f}"


def format_table(expenses: List[Dict[str, Any]]) -> str:
    """Formats a list of expenses as an aligned table."""
    if not expenses:
        return "No expenses found."

    headers = ["ID", "Date", "Description", "Category", "Amount"]

    rows = []
    for exp in expenses:
        rows.append([
            str(exp.get("id", "")),
            str(exp.get("date", "")),
            str(exp.get("description", "")),
            str(exp.get("category", "General")),
            format_amount(float(exp.get("amount", 0.0)))
        ])

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    # Format header and rows with 2 spaces between columns
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    data_lines = [
        "  ".join(val.ljust(col_widths[i]) for i, val in enumerate(row))
        for row in rows
    ]

    return "\n".join([header_line] + data_lines)


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def validate_positive_amount(amount_str: Any) -> float:
    """Parses and validates that an amount is a positive number (> 0)."""
    try:
        val = float(amount_str)
    except (ValueError, TypeError):
        raise ExpenseTrackerError(f"Invalid amount '{amount_str}'. Amount must be a valid number.")

    if val <= 0:
        raise ExpenseTrackerError("Amount must be a positive number greater than 0.")
    return val


def validate_description(description: Optional[str]) -> str:
    """Validates that a description is non-empty."""
    if description is None or not description.strip():
        raise ExpenseTrackerError("Description cannot be empty.")
    return description.strip()


def validate_month(month_val: Any) -> int:
    """Validates that month is an integer between 1 and 12."""
    try:
        month = int(month_val)
    except (ValueError, TypeError):
        raise ExpenseTrackerError(f"Invalid month '{month_val}'. Month must be an integer between 1 and 12.")

    if month < 1 or month > 12:
        raise ExpenseTrackerError(f"Invalid month '{month}'. Month must be an integer between 1 and 12.")
    return month


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

def handle_add(args: argparse.Namespace, data_file: str) -> int:
    """Handles adding a new expense."""
    desc = validate_description(args.description)
    amount = validate_positive_amount(args.amount)
    category = args.category.strip() if (args.category and args.category.strip()) else "General"

    data = load_data(data_file)

    expense_id = data["next_id"]
    today_date = datetime.date.today()
    date_str = today_date.isoformat()

    new_expense = {
        "id": expense_id,
        "date": date_str,
        "description": desc,
        "amount": amount,
        "category": category
    }

    # Check budget for current month & year
    current_year = today_date.year
    current_month = today_date.month
    month_name = calendar.month_name[current_month]

    # Calculate current month's expenses before addition
    monthly_expenses_before = sum(
        exp.get("amount", 0.0)
        for exp in data["expenses"]
        if exp.get("date", "").startswith(f"{current_year}-{current_month:02d}")
    )
    monthly_expenses_after = monthly_expenses_before + amount

    # Check if budget exists (check both YYYY-MM and simple month keys)
    budgets = data.get("budgets", {})
    budget_limit = budgets.get(f"{current_year}-{current_month:02d}")
    if budget_limit is None:
        budget_limit = budgets.get(str(current_month))

    data["expenses"].append(new_expense)
    data["next_id"] = expense_id + 1
    save_data(data, data_file)

    print(f"Expense added successfully (ID: {expense_id})")

    # Warn if adding this expense exceeds or is over the budget
    if budget_limit is not None and monthly_expenses_after > budget_limit:
        print(
            f"Warning: Monthly expenses for {month_name} ({format_amount(monthly_expenses_after)}) "
            f"have exceeded your budget of {format_amount(budget_limit)}!"
        )

    return 0


def handle_update(args: argparse.Namespace, data_file: str) -> int:
    """Handles updating an existing expense."""
    if args.description is None and args.amount is None and getattr(args, "category", None) is None:
        raise ExpenseTrackerError(
            "At least one of --description, --amount, or --category must be provided to update."
        )

    data = load_data(data_file)

    target_expense = None
    for exp in data["expenses"]:
        if exp.get("id") == args.id:
            target_expense = exp
            break

    if target_expense is None:
        raise ExpenseTrackerError(f"Expense with ID {args.id} not found.")

    if args.description is not None:
        target_expense["description"] = validate_description(args.description)

    if args.amount is not None:
        target_expense["amount"] = validate_positive_amount(args.amount)

    if getattr(args, "category", None) is not None:
        cat = args.category.strip()
        if not cat:
            raise ExpenseTrackerError("Category cannot be empty.")
        target_expense["category"] = cat

    save_data(data, data_file)
    print("Expense updated successfully")
    return 0


def handle_delete(args: argparse.Namespace, data_file: str) -> int:
    """Handles deleting an expense by ID."""
    data = load_data(data_file)

    initial_count = len(data["expenses"])
    data["expenses"] = [exp for exp in data["expenses"] if exp.get("id") != args.id]

    if len(data["expenses"]) == initial_count:
        raise ExpenseTrackerError(f"Expense with ID {args.id} not found.")

    # Note: next_id is intentionally NOT decremented or reset
    save_data(data, data_file)
    print("Expense deleted successfully")
    return 0


def handle_list(args: argparse.Namespace, data_file: str) -> int:
    """Handles listing expenses, optionally filtered by category."""
    data = load_data(data_file)
    expenses = data.get("expenses", [])

    if args.category:
        target_cat = args.category.strip().lower()
        expenses = [
            exp for exp in expenses
            if exp.get("category", "General").lower() == target_cat
        ]

    print(format_table(expenses))
    return 0


def handle_summary(args: argparse.Namespace, data_file: str) -> int:
    """Handles displaying total or monthly summary."""
    data = load_data(data_file)
    expenses = data.get("expenses", [])

    if args.month is not None:
        month = validate_month(args.month)
        current_year = datetime.date.today().year
        month_name = calendar.month_name[month]
        prefix = f"{current_year}-{month:02d}"

        total = sum(
            exp.get("amount", 0.0)
            for exp in expenses
            if exp.get("date", "").startswith(prefix)
        )
        print(f"Total expenses for {month_name}: {format_amount(total)}")
    else:
        total = sum(exp.get("amount", 0.0) for exp in expenses)
        print(f"Total expenses: {format_amount(total)}")

    return 0


def handle_budget(args: argparse.Namespace, data_file: str) -> int:
    """Handles setting a monthly budget."""
    month = validate_month(args.month)
    amount = validate_positive_amount(args.amount)

    data = load_data(data_file)
    current_year = datetime.date.today().year
    month_name = calendar.month_name[month]

    # Store under both standard month number and year-month
    key = f"{current_year}-{month:02d}"
    data["budgets"][key] = amount
    data["budgets"][str(month)] = amount

    save_data(data, data_file)
    print(f"Budget for {month_name} set to {format_amount(amount)}")
    return 0


def handle_export(args: argparse.Namespace, data_file: str) -> int:
    """Handles exporting expenses to a CSV file."""
    data = load_data(data_file)
    expenses = data.get("expenses", [])

    export_path = args.file
    if not export_path or not export_path.strip():
        raise ExpenseTrackerError("Export file path cannot be empty.")

    try:
        with open(export_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Date", "Description", "Category", "Amount"])
            for exp in expenses:
                writer.writerow([
                    exp.get("id"),
                    exp.get("date"),
                    exp.get("description"),
                    exp.get("category", "General"),
                    exp.get("amount")
                ])
    except OSError as e:
        raise ExpenseTrackerError(f"Failed to export expenses to '{export_path}': {e}")

    print(f"Expenses exported successfully to {export_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI Parser Setup & Main Entry Point
# ---------------------------------------------------------------------------

def create_parser() -> argparse.ArgumentParser:
    """Constructs and returns the command line argument parser."""
    parser = CleanArgumentParser(
        prog="expense-tracker",
        description="A command-line expense tracker application in Python."
    )
    parser.add_argument(
        "--data-file",
        dest="data_file",
        default=DEFAULT_DATA_FILE,
        help=argparse.SUPPRESS  # Internal option for testing/custom data file
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available commands"
    )

    # 1. add
    add_parser = subparsers.add_parser("add", help="Add a new expense")
    add_parser.add_argument("--description", required=True, help="Description of the expense")
    add_parser.add_argument("--amount", required=True, help="Expense amount (positive number)")
    add_parser.add_argument("--category", default="General", help="Expense category (default: General)")

    # 2. update
    update_parser = subparsers.add_parser("update", help="Update an existing expense")
    update_parser.add_argument("--id", type=int, required=True, help="Expense ID to update")
    update_parser.add_argument("--description", default=None, help="New description")
    update_parser.add_argument("--amount", default=None, help="New amount")
    update_parser.add_argument("--category", default=None, help="New category")

    # 3. delete
    delete_parser = subparsers.add_parser("delete", help="Delete an expense by ID")
    delete_parser.add_argument("--id", type=int, required=True, help="Expense ID to delete")

    # 4. list
    list_parser = subparsers.add_parser("list", help="List all expenses")
    list_parser.add_argument("--category", default=None, help="Filter expenses by category")

    # 5. summary
    summary_parser = subparsers.add_parser("summary", help="Show total or monthly summary")
    summary_parser.add_argument("--month", default=None, help="Month number (1-12) for monthly summary")

    # 6. budget
    budget_parser = subparsers.add_parser("budget", help="Set a monthly budget")
    budget_parser.add_argument("--month", required=True, help="Month number (1-12)")
    budget_parser.add_argument("--amount", required=True, help="Budget amount (positive number)")

    # 7. export
    export_parser = subparsers.add_parser("export", help="Export expenses to a CSV file")
    export_parser.add_argument("--file", required=True, help="Destination CSV file path")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    if argv is None:
        argv = sys.argv[1:]

    parser = create_parser()

    if not argv:
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

    command_handlers = {
        "add": handle_add,
        "update": handle_update,
        "delete": handle_delete,
        "list": handle_list,
        "summary": handle_summary,
        "budget": handle_budget,
        "export": handle_export,
    }

    handler = command_handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 0

    try:
        return handler(args, args.data_file)
    except ExpenseTrackerError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

