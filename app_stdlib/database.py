"""Database module using Python's built-in sqlite3."""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "appropriations.db")


def get_connection():
    """Get a database connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize the database schema."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with get_db() as conn:
        cursor = conn.cursor()

        # Create eligible_accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eligible_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subcommittee TEXT NOT NULL,
                subcategory TEXT,
                agency TEXT NOT NULL,
                account_name TEXT NOT NULL,
                is_new INTEGER DEFAULT 0,
                notes TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subcommittee, agency, account_name)
            )
        """)

        # Create requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fiscal_year INTEGER DEFAULT 2027,
                request_type TEXT NOT NULL CHECK(request_type IN ('cpf', 'programmatic', 'language')),
                subcommittee TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                requester_name TEXT,
                requester_email TEXT,
                requester_organization TEXT,
                requested_amount REAL,
                status TEXT DEFAULT 'draft',
                program_name TEXT,
                programmatic_justification TEXT,
                bill_section TEXT,
                proposed_language TEXT,
                language_justification TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create cpf_details table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cpf_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL UNIQUE,
                cpf_account_id INTEGER,
                tx11_nexus INTEGER DEFAULT 0,
                tx11_nexus_explanation TEXT,
                entity_type TEXT,
                entity_name TEXT,
                entity_address TEXT,
                project_name TEXT,
                project_address TEXT,
                project_description TEXT,
                requested_amount REAL,
                total_project_cost REAL,
                cost_share_amount REAL,
                cost_share_required INTEGER DEFAULT 0,
                cost_share_explanation TEXT,
                public_benefit_justification TEXT,
                tx11_priority_justification TEXT,
                stakeholders_support TEXT,
                eligibility_citations TEXT,
                timeline TEXT,
                authorized_in_law INTEGER DEFAULT 0,
                authorization_citation TEXT,
                support_letters_received INTEGER DEFAULT 0,
                selected INTEGER DEFAULT 0,
                selected_slot INTEGER,
                selected_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
                FOREIGN KEY (cpf_account_id) REFERENCES eligible_accounts(id)
            )
        """)

        # Create attachments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                content_type TEXT,
                attachment_type TEXT DEFAULT 'other',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_fiscal_year ON requests(fiscal_year)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_type ON requests(request_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_subcommittee ON requests(subcommittee)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_request ON attachments(request_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eligible_accounts_subcommittee ON eligible_accounts(subcommittee)")

        print("Database initialized successfully.")
