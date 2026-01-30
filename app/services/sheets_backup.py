"""
Google Sheets backup service for appropriations requests.
Automatically backs up new submissions to a Google Sheet for easy viewing/export.
"""
import json
import logging
from datetime import datetime
from typing import Optional, Any

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-load gspread to avoid import errors when not configured
_sheets_client = None
_worksheet = None


def _get_worksheet():
    """Get or create the Google Sheets worksheet connection."""
    global _sheets_client, _worksheet

    if not settings.google_sheets_enabled:
        return None

    if _worksheet is not None:
        return _worksheet

    if not settings.google_sheets_id or not settings.google_service_account_json:
        logger.warning("Google Sheets enabled but missing configuration")
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Parse service account JSON from environment variable
        creds_dict = json.loads(settings.google_service_account_json)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        _sheets_client = gspread.authorize(credentials)

        # Open the spreadsheet and get/create the Submissions worksheet
        spreadsheet = _sheets_client.open_by_key(settings.google_sheets_id)

        try:
            _worksheet = spreadsheet.worksheet("Submissions")
        except gspread.WorksheetNotFound:
            # Create worksheet with headers
            _worksheet = spreadsheet.add_worksheet(title="Submissions", rows=1000, cols=20)
            headers = [
                "ID", "Submitted At", "Request Type", "Subcommittee", "Title",
                "Description", "Requester Name", "Requester Email", "Organization",
                "Requested Amount", "Status", "Program Name", "Bill Section",
                "Proposed Language", "Entity Type", "Entity Name", "Project Name",
                "Project Location", "TX-11 Connection"
            ]
            _worksheet.append_row(headers)

        return _worksheet

    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        return None


def backup_request_to_sheets(request_data: dict, cpf_data: Optional[dict] = None) -> bool:
    """
    Backup a request to Google Sheets.

    Args:
        request_data: The main request data
        cpf_data: Optional CPF-specific data

    Returns:
        True if backup succeeded, False otherwise
    """
    worksheet = _get_worksheet()
    if worksheet is None:
        return False

    try:
        # Format the row data
        row = [
            request_data.get("id", ""),
            datetime.now().isoformat(),
            request_data.get("request_type", ""),
            request_data.get("subcommittee", ""),
            request_data.get("title", ""),
            request_data.get("description", "")[:500] if request_data.get("description") else "",
            request_data.get("requester_name", ""),
            request_data.get("requester_email", ""),
            request_data.get("requester_organization", ""),
            str(request_data.get("requested_amount", "")) if request_data.get("requested_amount") else "",
            request_data.get("status", "draft"),
            request_data.get("program_name", ""),
            request_data.get("bill_section", ""),
            request_data.get("proposed_language", "")[:500] if request_data.get("proposed_language") else "",
        ]

        # Add CPF-specific fields if available
        if cpf_data:
            row.extend([
                cpf_data.get("entity_type", ""),
                cpf_data.get("entity_name", ""),
                cpf_data.get("project_name", ""),
                cpf_data.get("project_address", ""),
                cpf_data.get("tx11_nexus_explanation", "")[:500] if cpf_data.get("tx11_nexus_explanation") else "",
            ])
        else:
            row.extend(["", "", "", "", ""])

        worksheet.append_row(row)
        logger.info(f"Backed up request {request_data.get('id')} to Google Sheets")
        return True

    except Exception as e:
        logger.error(f"Failed to backup to Google Sheets: {e}")
        return False


def backup_to_sheets_async(request_data: dict, cpf_data: Optional[dict] = None):
    """
    Non-blocking backup to Google Sheets.
    Failures are logged but don't affect the main request flow.
    """
    try:
        backup_request_to_sheets(request_data, cpf_data)
    except Exception as e:
        logger.error(f"Async backup failed: {e}")
