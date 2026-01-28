"""Seed script to load eligible accounts from JSON file."""

import json
import os
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import EligibleAccount


def load_eligible_accounts(db: Session, json_path: str) -> int:
    """Load eligible accounts from JSON file into database."""

    with open(json_path, "r") as f:
        data = json.load(f)

    accounts = data.get("accounts", [])
    loaded = 0

    for account_data in accounts:
        # Check if account already exists
        existing = db.query(EligibleAccount).filter(
            EligibleAccount.subcommittee == account_data["subcommittee"],
            EligibleAccount.agency == account_data["agency"],
            EligibleAccount.account_name == account_data["account_name"],
        ).first()

        if existing:
            continue

        account = EligibleAccount(
            subcommittee=account_data["subcommittee"],
            subcategory=account_data.get("subcategory"),
            agency=account_data["agency"],
            account_name=account_data["account_name"],
            is_new=account_data.get("is_new", False),
            notes=account_data.get("notes"),
            active=True,
        )
        db.add(account)
        loaded += 1

    db.commit()
    return loaded


def main():
    """Main entry point for seed script."""
    json_path = os.path.join(os.path.dirname(__file__), "..", "seed", "eligible_accounts_fy27.json")

    if not os.path.exists(json_path):
        print(f"Seed file not found: {json_path}")
        return

    db = SessionLocal()
    try:
        loaded = load_eligible_accounts(db, json_path)
        print(f"Loaded {loaded} eligible accounts from seed file")
    finally:
        db.close()


if __name__ == "__main__":
    main()
