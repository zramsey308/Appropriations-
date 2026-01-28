"""Business logic services using sqlite3."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from .database import get_db

ALLOWED_ENTITY_TYPES = [
    "state_government",
    "local_government",
    "tribal_government",
    "nonprofit",
    "public_higher_education",
    "special_district",
]

SUBCOMMITTEES = [
    "agriculture",
    "commerce_justice_science",
    "defense",
    "energy_water",
    "financial_services_general_government",
    "homeland_security",
    "interior_environment",
    "labor_hhs_education",
    "legislative_branch",
    "milcon_va",
    "state_foreign_operations",
    "transportation_hud",
]

MAX_SELECTED_SLOTS = 15


def dict_from_row(row) -> Optional[Dict[str, Any]]:
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)


# ============ REQUEST SERVICES ============

def create_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new request."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Validate required fields
        if "request_type" not in data or data["request_type"] not in ("cpf", "programmatic", "language"):
            raise ValueError("request_type must be 'cpf', 'programmatic', or 'language'")
        if "subcommittee" not in data or data["subcommittee"] not in SUBCOMMITTEES:
            raise ValueError(f"subcommittee must be one of: {', '.join(SUBCOMMITTEES)}")
        if "title" not in data or not data["title"]:
            raise ValueError("title is required")

        cursor.execute("""
            INSERT INTO requests (
                fiscal_year, request_type, subcommittee, title, description,
                requester_name, requester_email, requester_organization,
                requested_amount, status, program_name, programmatic_justification,
                bill_section, proposed_language, language_justification
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("fiscal_year", 2027),
            data["request_type"],
            data["subcommittee"],
            data["title"],
            data.get("description"),
            data.get("requester_name"),
            data.get("requester_email"),
            data.get("requester_organization"),
            data.get("requested_amount"),
            data.get("status", "draft"),
            data.get("program_name"),
            data.get("programmatic_justification"),
            data.get("bill_section"),
            data.get("proposed_language"),
            data.get("language_justification"),
        ))

        request_id = cursor.lastrowid

        cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        return dict_from_row(cursor.fetchone())


def get_request(request_id: int) -> Optional[Dict[str, Any]]:
    """Get a single request by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        return dict_from_row(cursor.fetchone())


def list_requests(
    fiscal_year: Optional[int] = None,
    request_type: Optional[str] = None,
    subcommittee: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """List requests with optional filters."""
    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM requests WHERE 1=1"
        params = []

        if fiscal_year:
            query += " AND fiscal_year = ?"
            params.append(fiscal_year)
        if request_type:
            query += " AND request_type = ?"
            params.append(request_type)
        if subcommittee:
            query += " AND subcommittee = ?"
            params.append(subcommittee)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, skip])

        cursor.execute(query, params)
        return [dict_from_row(row) for row in cursor.fetchall()]


def update_request(request_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a request."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if request exists
        cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        if not cursor.fetchone():
            return None

        # Build update query dynamically
        allowed_fields = [
            "title", "description", "requester_name", "requester_email",
            "requester_organization", "requested_amount", "status",
            "program_name", "programmatic_justification", "bill_section",
            "proposed_language", "language_justification"
        ]

        updates = []
        params = []
        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = ?")
                params.append(data[field])

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(request_id)

            cursor.execute(
                f"UPDATE requests SET {', '.join(updates)} WHERE id = ?",
                params
            )

        cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        return dict_from_row(cursor.fetchone())


def delete_request(request_id: int) -> bool:
    """Delete a request."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requests WHERE id = ?", (request_id,))
        return cursor.rowcount > 0


# ============ CPF DETAILS SERVICES ============

def get_cpf_details(request_id: int) -> Optional[Dict[str, Any]]:
    """Get CPF details for a request."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cpf_details WHERE request_id = ?", (request_id,))
        return dict_from_row(cursor.fetchone())


def create_or_update_cpf_details(request_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create or update CPF details."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify request exists and is CPF type
        cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        request = cursor.fetchone()
        if not request:
            return None
        if request["request_type"] != "cpf":
            raise ValueError("Request must be of type 'cpf' to have CPF details")

        # Check if CPF details exist
        cursor.execute("SELECT * FROM cpf_details WHERE request_id = ?", (request_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing
            allowed_fields = [
                "cpf_account_id", "tx11_nexus", "tx11_nexus_explanation",
                "entity_type", "entity_name", "entity_address",
                "project_name", "project_address", "project_description",
                "requested_amount", "total_project_cost", "cost_share_amount",
                "cost_share_required", "cost_share_explanation",
                "public_benefit_justification", "tx11_priority_justification",
                "stakeholders_support", "eligibility_citations", "timeline",
                "authorized_in_law", "authorization_citation"
            ]

            updates = []
            params = []
            for field in allowed_fields:
                if field in data:
                    updates.append(f"{field} = ?")
                    # Convert booleans to integers for SQLite
                    value = data[field]
                    if isinstance(value, bool):
                        value = 1 if value else 0
                    params.append(value)

            if updates:
                updates.append("updated_at = ?")
                params.append(datetime.utcnow().isoformat())
                params.append(request_id)

                cursor.execute(
                    f"UPDATE cpf_details SET {', '.join(updates)} WHERE request_id = ?",
                    params
                )
        else:
            # Create new
            # Convert booleans
            for key in ["tx11_nexus", "cost_share_required", "authorized_in_law"]:
                if key in data and isinstance(data[key], bool):
                    data[key] = 1 if data[key] else 0

            cursor.execute("""
                INSERT INTO cpf_details (
                    request_id, cpf_account_id, tx11_nexus, tx11_nexus_explanation,
                    entity_type, entity_name, entity_address,
                    project_name, project_address, project_description,
                    requested_amount, total_project_cost, cost_share_amount,
                    cost_share_required, cost_share_explanation,
                    public_benefit_justification, tx11_priority_justification,
                    stakeholders_support, eligibility_citations, timeline,
                    authorized_in_law, authorization_citation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id,
                data.get("cpf_account_id"),
                data.get("tx11_nexus", 0),
                data.get("tx11_nexus_explanation"),
                data.get("entity_type"),
                data.get("entity_name"),
                data.get("entity_address"),
                data.get("project_name"),
                data.get("project_address"),
                data.get("project_description"),
                data.get("requested_amount"),
                data.get("total_project_cost"),
                data.get("cost_share_amount"),
                data.get("cost_share_required", 0),
                data.get("cost_share_explanation"),
                data.get("public_benefit_justification"),
                data.get("tx11_priority_justification"),
                data.get("stakeholders_support"),
                data.get("eligibility_citations"),
                data.get("timeline"),
                data.get("authorized_in_law", 0),
                data.get("authorization_citation"),
            ))

        cursor.execute("SELECT * FROM cpf_details WHERE request_id = ?", (request_id,))
        return dict_from_row(cursor.fetchone())


def validate_cpf(request_id: int) -> Dict[str, Any]:
    """Validate CPF compliance."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
        request = dict_from_row(cursor.fetchone())
        if not request:
            return {"passed": False, "items": [], "missing_requirements": ["Request not found"]}

        cursor.execute("SELECT * FROM cpf_details WHERE request_id = ?", (request_id,))
        cpf = dict_from_row(cursor.fetchone())
        if not cpf:
            return {"passed": False, "items": [], "missing_requirements": ["CPF details not found"]}

        items = []
        missing = []

        # 1. TX-11 nexus
        tx11_passed = cpf["tx11_nexus"] == 1
        items.append({
            "field": "tx11_nexus",
            "requirement": "TX-11 nexus must be true",
            "passed": tx11_passed,
            "message": "TX-11 nexus confirmed" if tx11_passed else "TX-11 nexus not confirmed"
        })
        if not tx11_passed:
            missing.append("TX-11 nexus must be confirmed")

        # 2. Entity type
        entity_passed = cpf.get("entity_type") in ALLOWED_ENTITY_TYPES
        items.append({
            "field": "entity_type",
            "requirement": f"Entity type must be one of: {', '.join(ALLOWED_ENTITY_TYPES)}",
            "passed": entity_passed,
            "message": f"Entity type is valid: {cpf.get('entity_type')}" if entity_passed else "Invalid entity type"
        })
        if not entity_passed:
            missing.append("Entity type must be set to an allowed type")

        # 3. CPF account validation
        account_passed = False
        account_message = "CPF account not set"
        if cpf.get("cpf_account_id"):
            cursor.execute("SELECT * FROM eligible_accounts WHERE id = ?", (cpf["cpf_account_id"],))
            account = dict_from_row(cursor.fetchone())
            if account:
                if account["subcommittee"] == request["subcommittee"]:
                    if account["active"]:
                        account_passed = True
                        account_message = f"Valid CPF account: {account['account_name']}"
                    else:
                        account_message = "CPF account is not active"
                else:
                    account_message = f"Account subcommittee ({account['subcommittee']}) doesn't match request ({request['subcommittee']})"
            else:
                account_message = "CPF account not found"

        items.append({
            "field": "cpf_account_id",
            "requirement": "CPF account must be valid, active, and match subcommittee",
            "passed": account_passed,
            "message": account_message
        })
        if not account_passed:
            missing.append("Valid CPF account matching request subcommittee required")

        # 4. Support letters (>= 3)
        letters = cpf.get("support_letters_received", 0)
        letters_passed = letters >= 3
        items.append({
            "field": "support_letters_received",
            "requirement": "At least 3 support letters required",
            "passed": letters_passed,
            "message": f"{letters} support letters received" if letters_passed else f"Only {letters} support letters (need 3)"
        })
        if not letters_passed:
            missing.append(f"Need at least 3 support letters (have {letters})")

        # 5. Cost share explanation
        cost_share_passed = True
        if cpf.get("cost_share_required"):
            cost_share_passed = bool(cpf.get("cost_share_explanation", "").strip())
        items.append({
            "field": "cost_share_explanation",
            "requirement": "Cost share explanation required if cost share is required",
            "passed": cost_share_passed,
            "message": "Cost share OK" if cost_share_passed else "Cost share explanation required"
        })
        if not cost_share_passed:
            missing.append("Cost share explanation must be provided")

        overall_passed = all(item["passed"] for item in items)

        return {
            "passed": overall_passed,
            "items": items,
            "missing_requirements": missing
        }


def select_cpf(request_id: int, slot: Optional[int] = None) -> Dict[str, Any]:
    """Select a CPF request for funding."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM cpf_details WHERE request_id = ?", (request_id,))
        cpf = dict_from_row(cursor.fetchone())
        if not cpf:
            raise ValueError("CPF details not found")

        if cpf["selected"]:
            raise ValueError(f"Already selected in slot {cpf['selected_slot']}")

        # Check cap
        cursor.execute("SELECT COUNT(*) as cnt FROM cpf_details WHERE selected = 1")
        count = cursor.fetchone()["cnt"]
        if count >= MAX_SELECTED_SLOTS:
            raise ValueError(f"Maximum selection cap of {MAX_SELECTED_SLOTS} reached")

        # Validate first
        validation = validate_cpf(request_id)
        if not validation["passed"]:
            raise ValueError(f"Validation failed: {', '.join(validation['missing_requirements'])}")

        # Determine slot
        if slot is not None:
            if slot < 1 or slot > MAX_SELECTED_SLOTS:
                raise ValueError(f"Slot must be 1-{MAX_SELECTED_SLOTS}")
            cursor.execute("SELECT * FROM cpf_details WHERE selected_slot = ?", (slot,))
            if cursor.fetchone():
                raise ValueError(f"Slot {slot} is already taken")
            assigned_slot = slot
        else:
            cursor.execute("SELECT selected_slot FROM cpf_details WHERE selected_slot IS NOT NULL")
            used = {row["selected_slot"] for row in cursor.fetchall()}
            assigned_slot = None
            for s in range(1, MAX_SELECTED_SLOTS + 1):
                if s not in used:
                    assigned_slot = s
                    break
            if assigned_slot is None:
                raise ValueError("No slots available")

        # Update CPF details
        cursor.execute("""
            UPDATE cpf_details
            SET selected = 1, selected_slot = ?, selected_at = ?
            WHERE request_id = ?
        """, (assigned_slot, datetime.utcnow().isoformat(), request_id))

        # Update request status
        cursor.execute("UPDATE requests SET status = 'selected' WHERE id = ?", (request_id,))

        cursor.execute("SELECT * FROM cpf_details WHERE request_id = ?", (request_id,))
        return dict_from_row(cursor.fetchone())


def increment_support_letters(request_id: int) -> Optional[Dict[str, Any]]:
    """Increment support letters count for a CPF request."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cpf_details
            SET support_letters_received = support_letters_received + 1
            WHERE request_id = ?
        """, (request_id,))

        cursor.execute("SELECT * FROM cpf_details WHERE request_id = ?", (request_id,))
        return dict_from_row(cursor.fetchone())


# ============ ELIGIBLE ACCOUNTS SERVICES ============

def list_eligible_accounts(
    subcommittee: Optional[str] = None,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    """List eligible accounts."""
    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM eligible_accounts WHERE 1=1"
        params = []

        if subcommittee:
            query += " AND subcommittee = ?"
            params.append(subcommittee)
        if active_only:
            query += " AND active = 1"

        query += " ORDER BY subcommittee, agency, account_name"

        cursor.execute(query, params)
        return [dict_from_row(row) for row in cursor.fetchall()]


def get_eligible_account(account_id: int) -> Optional[Dict[str, Any]]:
    """Get a single eligible account."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM eligible_accounts WHERE id = ?", (account_id,))
        return dict_from_row(cursor.fetchone())


# ============ DASHBOARD SERVICES ============

def get_dashboard_summary(fiscal_year: int = 2027) -> Dict[str, Any]:
    """Get dashboard summary statistics."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Total counts by type
        cursor.execute("""
            SELECT request_type, COUNT(*) as count
            FROM requests WHERE fiscal_year = ?
            GROUP BY request_type
        """, (fiscal_year,))
        by_type = {row["request_type"]: row["count"] for row in cursor.fetchall()}

        # Counts by subcommittee
        cursor.execute("""
            SELECT subcommittee, COUNT(*) as count
            FROM requests WHERE fiscal_year = ?
            GROUP BY subcommittee
        """, (fiscal_year,))
        by_subcommittee = {row["subcommittee"]: row["count"] for row in cursor.fetchall()}

        # Counts by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM requests WHERE fiscal_year = ?
            GROUP BY status
        """, (fiscal_year,))
        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

        # CPF selection stats
        cursor.execute("""
            SELECT COUNT(*) as selected,
                   SUM(CASE WHEN selected = 0 THEN 1 ELSE 0 END) as pending
            FROM cpf_details cd
            JOIN requests r ON cd.request_id = r.id
            WHERE r.fiscal_year = ?
        """, (fiscal_year,))
        cpf_row = cursor.fetchone()

        # Total requested amount
        cursor.execute("""
            SELECT SUM(requested_amount) as total
            FROM requests WHERE fiscal_year = ?
        """, (fiscal_year,))
        total_amount = cursor.fetchone()["total"] or 0

        return {
            "fiscal_year": fiscal_year,
            "total_requests": sum(by_type.values()),
            "by_type": by_type,
            "by_subcommittee": by_subcommittee,
            "by_status": by_status,
            "cpf_selected": cpf_row["selected"] if cpf_row else 0,
            "cpf_slots_remaining": MAX_SELECTED_SLOTS - (cpf_row["selected"] if cpf_row else 0),
            "total_requested_amount": total_amount
        }
