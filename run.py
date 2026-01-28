#!/usr/bin/env python
"""Simple script to initialize the database and start the server."""

import os
import sys

def main():
    # Ensure data directory exists
    os.makedirs("data/attachments", exist_ok=True)

    # Run migrations
    print("Running database migrations...")
    import subprocess
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Migration error: {result.stderr}")
        return 1
    print("Migrations complete.")

    # Seed accounts
    print("Seeding eligible accounts...")
    from app.seed_accounts import main as seed_main
    seed_main()

    # Start server
    print("\nStarting server at http://localhost:8080")
    print("API docs at http://localhost:8080/docs")
    print("Press Ctrl+C to stop\n")

    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
