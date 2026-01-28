#!/usr/bin/env python
"""
FY27 Appropriations Tracker - Standard Library Only Version

Run this script to start the server. No external packages required!
Uses only Python's built-in modules: sqlite3, http.server, json, etc.

Usage:
    python run_stdlib.py
"""

import os
import sys

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    print("=" * 60)
    print("  FY27 Appropriations Tracker")
    print("  Standard Library Only Version (No pip required!)")
    print("=" * 60)
    print()

    # Ensure data directories exist
    os.makedirs("data/attachments", exist_ok=True)
    print("[1/3] Data directories created")

    # Initialize database
    print("[2/3] Initializing database...")
    from app_stdlib.database import init_database
    init_database()

    # Seed eligible accounts
    print("[3/3] Seeding eligible accounts...")
    from app_stdlib.seed import main as seed_main
    seed_main()

    print()
    print("=" * 60)
    print("  Server starting on http://localhost:8080")
    print("  API docs at http://localhost:8080/docs")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    # Start server
    from app_stdlib.server import run_server
    run_server(port=8080)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
