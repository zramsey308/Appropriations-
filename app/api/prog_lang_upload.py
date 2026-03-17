"""
Programmatic & Language JSON Schema Upload endpoint.

Accepts structured JSON from ChatGPT doc parsing for programmatic and language
requests, supporting both single and bulk uploads.

Schema keys (programmatic):
  metadata, organization, point_of_contact, request_details, justification,
  prior_history, other_offices

Schema keys (language):
  metadata, organization, point_of_contact, bill_details, proposed_language,
  justification, prior_history, other_offices
"""
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.requests import Request as StarletteRequest

from app.db import get_db
from app.models import Request
from app.services.docx_parser import map_subcommittee

router = APIRouter()


# ── Helpers (shared with cpf_upload) ──────────────────────

def _parse_amount(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    cleaned = str(value).strip()
    if not cleaned:
        return None
    m = re.match(r"^\$?([\d,.]+)\s*[Mm](?:illion)?$", cleaned)
    if m:
        return int(float(m.group(1).replace(",", "")) * 1_000_000)
    m = re.match(r"^\$?([\d,.]+)\s*[Kk]$", cleaned)
    if m:
        return int(float(m.group(1).replace(",", "")) * 1_000)
    stripped = re.sub(r"[$,\s]", "", cleaned)
    try:
        return int(float(stripped))
    except (ValueError, OverflowError):
        return None


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _get(obj: Any, *keys: str, default: Any = None) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current if current is not None else default


# ── Response models ───────────────────────────────────────

class UploadResult(BaseModel):
    id: int
    title: str
    request_type: str
    subcommittee: str
    organization: str
    amount: Optional[int] = None
    status: str


class BulkUploadResponse(BaseModel):
    created: int
    requests: list[UploadResult]
    errors: list[str]


# ── Create from JSON schema ──────────────────────────────

def _create_from_prog_lang_schema(data: dict, db: Session) -> dict:
    """Create a Request from a programmatic/language JSON schema.

    Supports both:
    - Nested schema: request_details, bill_details, justification, etc.
    - Flat schema: top-level program_name, agency, bureau, etc.
    """
    def _as_dict(val, fallback_key="value"):
        """Ensure value is a dict; wrap strings/scalars into a dict."""
        if isinstance(val, dict):
            return val
        if val:
            return {fallback_key: val}
        return {}

    metadata = _as_dict(data.get("metadata"))
    portal = _as_dict(data.get("submission_portal_fields"))
    committee_sub = _as_dict(data.get("committee_submission"))
    org_raw = data.get("organization") or data.get("requesting_organization") or {}
    org = _as_dict(org_raw, "name")
    poc = _as_dict(data.get("point_of_contact"), "name")
    request_details = _as_dict(data.get("request_details"))
    bill = _as_dict(data.get("bill_details"))
    justification = _as_dict(data.get("justification"), "justification")
    prior = _as_dict(data.get("prior_history"), "prior_submissions")
    other = _as_dict(data.get("other_offices"), "other_members")
    lang_field = data.get("proposed_language") or data.get("proposal_text")

    # proposed_language can be a dict (nested schema) or a string (flat schema)
    if isinstance(lang_field, dict):
        proposed_text = (
            _str(lang_field.get("text"))
            or _str(lang_field.get("bill_language"))
        )
    else:
        proposed_text = _str(lang_field) if lang_field else ""

    # Also check nested locations (committee_submission.report_language, etc.)
    if not proposed_text:
        proposed_text = (
            _str(committee_sub.get("report_language"))
            or _str(committee_sub.get("bill_language"))
            or _str(data.get("proposed_language_text"))
            or _str(request_details.get("proposed_language"))
        )

    # Determine type
    raw_type = _str(
        portal.get("request_type")
        or metadata.get("request_type")
        or data.get("request_type")
        or ""
    ).lower()
    # Normalize: "report language" → "language", "programmatic request" → "programmatic"
    if "language" in raw_type or "report" in raw_type:
        request_type = "language"
    elif "programmatic" in raw_type:
        request_type = "programmatic"
    else:
        request_type = "language" if proposed_text else "programmatic"

    # Subcommittee (check portal fields, nested, and flat, including appropriations_bill)
    raw_sub = (
        _str(portal.get("subcommittee"))
        or _str(request_details.get("subcommittee"))
        or _str(request_details.get("appropriations_bill"))
        or _str(bill.get("appropriations_bill"))
        or _str(bill.get("subcommittee"))
        or _str(metadata.get("subcommittee"))
        or _str(metadata.get("bill"))
        or _str(data.get("subcommittee"))
        or _str(data.get("appropriations_bill"))
        or _str(data.get("committee"))
    )
    subcommittee = map_subcommittee(raw_sub)
    if not subcommittee:
        subcommittee = map_subcommittee(
            _str(portal.get("agency"))
            or _str(request_details.get("agency"))
            or _str(data.get("agency"))
        )
    if not subcommittee:
        subcommittee = "agriculture"

    # Title (check portal, nested, and flat, including program_title)
    title = (
        _str(request_details.get("program_title"))
        or _str(request_details.get("program_name"))
        or _str(data.get("program_name"))
        or _str(data.get("project_program_name"))
        or _str(data.get("program_or_project_name"))
        or _str(data.get("program_title"))
        or _str(request_details.get("title"))
        or _str(bill.get("title"))
        or _str(data.get("title"))
        or _str(metadata.get("title"))
        or _str(metadata.get("source_document"))
        or f"Imported {request_type.capitalize()} Request"
    )

    amount = _parse_amount(
        request_details.get("requested_amount")
        or data.get("requested_amount")
        or data.get("funding_amount_requested")
        or data.get("funding_requested")
        or request_details.get("last_fy_amount")
        or request_details.get("presidents_budget_amount")
    )

    fy = _get(metadata, "fiscal_year", default=None) or data.get("fiscal_year") or 2027
    if isinstance(fy, str):
        import re as _re
        digits = _re.sub(r"[^0-9]", "", fy)
        fy = int(digits[-4:]) if len(digits) >= 4 else 2027

    description = (
        _str(request_details.get("program_description"))
        or _str(request_details.get("description"))
        or _str(request_details.get("request_description"))
        or _str(data.get("program_description"))
        or _str(data.get("description"))
        or _str(data.get("summary"))
        or _str(justification.get("problem_statement"))
        or _str(justification.get("justification"))
        or ""
    )

    poc_name = _str(poc.get("name")) or _str(metadata.get("contact_name"))
    if not poc_name:
        first = _str(poc.get("first_name"))
        last = _str(poc.get("last_name"))
        poc_name = f"{first} {last}".strip()

    # Other members: merge various field names
    other_members_parts = []
    for v in [
        other.get("other_members"),
        other.get("other_members_receiving_request"),
        data.get("other_members"),
        data.get("additional_congressional_offices"),
    ]:
        if v:
            other_members_parts.append(_str(v))
    # committee_engagement may be a list
    committee_eng = data.get("committee_engagement") or []
    if isinstance(committee_eng, list):
        other_members_parts.extend(str(c) for c in committee_eng)
    elif committee_eng:
        other_members_parts.append(_str(committee_eng))
    other_members_str = "; ".join(p for p in other_members_parts if p)

    # Defense programmatic fields
    other_offices_raw = data.get("other_offices_submitted_to") or []
    if isinstance(other_offices_raw, list):
        other_offices_str = "; ".join(str(o) for o in other_offices_raw if o)
    else:
        other_offices_str = _str(other_offices_raw)
    if other_offices_str and other_members_str:
        other_members_str = other_members_str + "; " + other_offices_str
    elif other_offices_str:
        other_members_str = other_offices_str

    request = Request(
        fiscal_year=fy,
        request_type=request_type,
        subcommittee=subcommittee,
        status="submitted",
        title=title,
        description=description,
        requester_name=poc_name or _str(data.get("contact_name")),
        requester_email=_str(poc.get("email") or metadata.get("contact_email") or data.get("contact_email")),
        requester_phone=_str(poc.get("phone") or poc.get("business_phone") or metadata.get("contact_phone") or data.get("contact_phone")),
        requester_organization=_str(
            org.get("name") or org.get("organization_name")
            or poc.get("organization") or metadata.get("organization")
            or data.get("organization")
        ),
        requested_amount=amount,
        agency=_str(portal.get("agency") or request_details.get("agency") or data.get("agency")),
        bureau=_str(portal.get("bureau") or request_details.get("bureau") or data.get("bureau")),
        account=_str(portal.get("account") or request_details.get("account") or data.get("account")),
        program_funding=_str(
            request_details.get("program_funding")
            or portal.get("program_funding")
            or data.get("program_funding")
            or data.get("fy26_funding_status")
        ),
        program_name=_str(
            request_details.get("program_title")
            or request_details.get("program_name")
            or data.get("program_name")
            or data.get("program_or_project_name")
            or data.get("program_title")
        ),
        programmatic_justification=_str(
            request_details.get("program_description")
            or justification.get("goals_outcomes")
            or justification.get("justification")
            or data.get("justification")
            or data.get("program_description")
        ),
        bill_section=_str(bill.get("section") or request_details.get("bill_section") or data.get("bill_section")),
        proposed_language=proposed_text,
        language_justification=_str(
            data.get("language_justification")
            or data.get("justification")
            or justification.get("problem_statement")
            or request_details.get("program_description")
        ),
        priority_rank=_str(request_details.get("priority") or metadata.get("priority") or data.get("priority_rank")),
        problem_statement=_str(
            justification.get("problem_statement")
            or data.get("problem_statement")
            or data.get("tx11_impact")
        ),
        goals_outcomes=_str(justification.get("goals_outcomes") or data.get("goals_outcomes")),
        other_members=other_members_str,
        prior_year_submission=bool(prior.get("prior_submissions") or prior.get("prior_year_submission") or data.get("prior_year_submission") or data.get("prior_year_requests")),
        prior_year_details=_str(prior.get("prior_submissions") or prior.get("prior_year_details") or data.get("prior_year_details") or data.get("prior_year_requests")),
        # Defense programmatic fields
        component=_str(data.get("component") or request_details.get("component")),
        budget_activity=_str(data.get("budget_activity") or request_details.get("budget_activity")),
        program_element=_str(data.get("program_element") or request_details.get("program_element")),
        line_number=_str(data.get("line_number") or request_details.get("line_number")),
        project_program_name=_str(data.get("project_program_name") or request_details.get("project_program_name")),
        funding_amount_enacted_previous_year=_parse_amount(data.get("funding_amount_enacted_previous_year") or request_details.get("funding_amount_enacted_previous_year")),
        funding_amount_presidents_budget=_parse_amount(data.get("funding_amount_presidents_budget") or request_details.get("funding_amount_presidents_budget")),
        location=_str(data.get("location") or request_details.get("location")),
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    return {
        "id": request.id,
        "title": request.title,
        "request_type": request.request_type,
        "subcommittee": request.subcommittee,
        "organization": request.requester_organization,
        "amount": request.requested_amount,
        "status": "submitted",
    }


# ── Endpoints ─────────────────────────────────────────────

@router.post("/programmatic-json", response_model=BulkUploadResponse)
async def upload_programmatic_json(
    request: StarletteRequest,
    db: Session = Depends(get_db),
):
    """Upload one or more programmatic/language requests in JSON schema.

    Accepts either a single JSON object or an array of them.
    Automatically detects whether each record is programmatic or language
    based on the presence of proposed_language fields.
    """
    payload = await request.json()
    items = payload if isinstance(payload, list) else [payload]
    results: list[dict] = []
    errors: list[str] = []

    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item {i}: expected a JSON object")
            continue
        try:
            result = _create_from_prog_lang_schema(item, db)
            results.append(result)
        except Exception as e:
            db.rollback()
            errors.append(f"Item {i}: {str(e)}")

    return BulkUploadResponse(created=len(results), requests=results, errors=errors)
