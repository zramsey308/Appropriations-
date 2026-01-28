"""Seed script to load eligible accounts from JSON file."""

import json
import os
from .database import get_db


def load_eligible_accounts(json_path: str) -> int:
    """Load eligible accounts from JSON file into database."""
    with open(json_path, "r") as f:
        data = json.load(f)

    accounts = data.get("accounts", [])
    loaded = 0

    with get_db() as conn:
        cursor = conn.cursor()

        for account_data in accounts:
            # Check if account already exists
            cursor.execute("""
                SELECT id FROM eligible_accounts
                WHERE subcommittee = ? AND agency = ? AND account_name = ?
            """, (
                account_data["subcommittee"],
                account_data["agency"],
                account_data["account_name"]
            ))

            if cursor.fetchone():
                continue

            cursor.execute("""
                INSERT INTO eligible_accounts (
                    subcommittee, subcategory, agency, account_name, is_new, notes, active
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                account_data["subcommittee"],
                account_data.get("subcategory"),
                account_data["agency"],
                account_data["account_name"],
                1 if account_data.get("is_new") else 0,
                account_data.get("notes")
            ))
            loaded += 1

    return loaded


def main():
    """Main entry point for seed script."""
    json_path = os.path.join(os.path.dirname(__file__), "..", "seed", "eligible_accounts_fy27.json")

    if not os.path.exists(json_path):
        print(f"Seed file not found: {json_path}")
        return 0

    loaded = load_eligible_accounts(json_path)
    print(f"Loaded {loaded} eligible accounts from seed file")
    return loaded


if __name__ == "__main__":
    main()
