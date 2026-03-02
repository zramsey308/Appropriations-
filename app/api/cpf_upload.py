"""
CPF JSON Schema Upload endpoint.

Accepts the structured cpf_record JSON schema (from ChatGPT doc parsing)
and creates Request + CPFDetails records. Also provides CSV export.

Schema keys:
  metadata, requesting_organization, point_of_contact, project,
  narratives, support, status_and_eligibility, timeline_and_future_funding,
  authorization_and_budget, risk_and_priority, other_offices, compliance, flags
"""
import csv
import io
import re
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.requests import Request as StarletteRequest

from app.db import get_db
from app.models import Request, CPFDetails, EligibleAccount
from app.services.docx_parser import map_subcommittee
from app.api.upload import _best_eligible_account_match

router = APIRouter()


# ── Amount parsing ────────────────────────────────────────

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
    m = re.match(r"^\$?([\d,.]+)\s*[Bb](?:illion)?$", cleaned)
    if m:
        return int(float(m.group(1).replace(",", "")) * 1_000_000_000)
    stripped = re.sub(r"[$,\s]", "", cleaned)
    try:
        return int(float(stripped))
    except (ValueError, OverflowError):
        return None


# ── Entity type normalization ─────────────────────────────

def _normalize_entity_type(raw: str) -> Optional[str]:
    v = (raw or "").lower()
    if "nonprofit" in v or "501" in v or "non-profit" in v:
        return "nonprofit_501c3"
    if "tribal" in v:
        return "state_local_tribal_government"
    if any(kw in v for kw in ("city", "county", "state", "local", "government", "municipal")):
        return "state_local_tribal_government"
    if "public" in v or "university" in v or "college" in v or "higher ed" in v:
        return "public_entity"
    return None


# ── Helpers ───────────────────────────────────────────────

def _get(obj: Any, *keys: str, default: Any = None) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current if current is not None else default


def _bool_field(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s not in ("", "n/a", "no", "none", "false", "null")


def _str_field(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_citations(status_elig: dict) -> str:
    citations = status_elig.get("citations") or []
    parts = []
    justification = _str_field(status_elig.get("eligibility_justification"))
    if justification:
        parts.append(justification)
    for c in citations:
        if isinstance(c, dict) and c.get("citation_text"):
            parts.append(c["citation_text"])
    return "; ".join(parts)


# ── Pydantic models ──────────────────────────────────────

class CPFUploadResult(BaseModel):
    id: int
    title: str
    request_type: str
    subcommittee: str
    organization: str
    amount: Optional[int] = None
    status: str


class CPFUploadResponse(BaseModel):
    created: int
    requests: list[CPFUploadResult]
    errors: list[str]


# ── Create from schema ───────────────────────────────────

def _create_from_cpf_schema(data: dict, db: Session) -> dict:
    """Create a Request + CPFDetails from the ChatGPT cpf_record schema."""
    metadata = data.get("metadata") or {}
    org = data.get("requesting_organization") or {}
    poc = data.get("point_of_contact") or {}
    project = data.get("project") or {}
    narratives = data.get("narratives") or {}
    support = data.get("support") or {}
    status_elig = data.get("status_and_eligibility") or {}
    timeline = data.get("timeline_and_future_funding") or {}
    auth = data.get("authorization_and_budget") or {}
    risk = data.get("risk_and_priority") or {}
    other = data.get("other_offices") or {}
    compliance = data.get("compliance") or {}
    flags = data.get("flags") or []

    # Subcommittee resolution
    raw_sub = (
        _str_field(project.get("subcommittee_normalized"))
        or _str_field(project.get("subcommittee"))
    )
    subcommittee = map_subcommittee(raw_sub)
    if not subcommittee:
        subcommittee = map_subcommittee(_str_field(project.get("agency")))
    if not subcommittee:
        subcommittee = "agriculture"

    title = (
        _str_field(project.get("project_name"))
        or _str_field(project.get("project_summary_line"))
        or "Imported CPF Request"
    )
    amount = _parse_amount(
        project.get("requested_amount") or project.get("total_funding_request")
    )
    total_cost = _parse_amount(project.get("total_project_cost"))
    fy = _get(metadata, "fiscal_year", default=2027) or 2027
    description = (
        _str_field(project.get("purpose"))
        or _str_field(project.get("project_summary_line"))
    )

    # Entity type
    entity_type_raw = (
        _str_field(org.get("entity_type_raw"))
        or _str_field(org.get("entity_type_normalized"))
    )
    entity_type = _normalize_entity_type(entity_type_raw)

    request = Request(
        fiscal_year=fy,
        request_type="cpf",
        subcommittee=subcommittee,
        status="submitted",
        title=title,
        description=description,
        requester_name=_str_field(poc.get("name")),
        requester_email=_str_field(poc.get("email")),
        requester_phone=_str_field(poc.get("phone")),
        requester_organization=_str_field(org.get("name")),
        requested_amount=amount,
        agency=_str_field(project.get("agency")),
        priority_rank=_str_field(risk.get("priority_rank_if_multiple")) or None,
    )
    db.add(request)
    db.flush()

    # Eligible account matching
    cpf_account_id = None
    eligible_raw = _str_field(project.get("eligible_account"))
    agency_raw = _str_field(project.get("agency"))
    if eligible_raw or agency_raw:
        accounts = db.query(EligibleAccount).filter(
            EligibleAccount.subcommittee == subcommittee
        ).all()
        cpf_account_id = _best_eligible_account_match(accounts, eligible_raw, agency_raw)

    # Stakeholders
    stakeholders_list = support.get("stakeholders") or []
    stakeholders_str = (
        "; ".join(stakeholders_list)
        if isinstance(stakeholders_list, list)
        else _str_field(stakeholders_list)
    )

    cpf = CPFDetails(
        request_id=request.id,
        cpf_account_id=cpf_account_id,
        tx11_nexus=_bool_field(compliance.get("tx11_based_claimed")),
        tx11_nexus_explanation=_str_field(
            compliance.get("tx11_benefit_claimed")
            or narratives.get("district_priority_justification")
        ),
        entity_type=entity_type,
        entity_name=_str_field(org.get("name")),
        entity_address=_str_field(org.get("address")),
        project_name=title,
        project_address=_str_field(project.get("project_address")),
        project_description=description,
        requested_amount=amount,
        total_project_cost=total_cost,
        cost_share_required=_bool_field(auth.get("non_federal_cost_share_required")),
        cost_share_explanation=_str_field(auth.get("cost_share_explanation")),
        public_benefit_justification=_str_field(
            narratives.get("public_benefit_and_taxpayer_rationale")
        ),
        tx11_priority_justification=_str_field(
            narratives.get("district_priority_justification")
        ),
        stakeholders_support=stakeholders_str,
        support_letters_received=int(
            compliance.get("letters_of_support_count_mentioned") or 0
        ) if isinstance(compliance.get("letters_of_support_count_mentioned"), (int, float)) else 0,
        eligibility_citations=_extract_citations(status_elig),
        timeline=_str_field(timeline.get("timeline_to_complete")),
        future_federal_funding=_bool_field(
            timeline.get("requires_future_federal_funding")
        ),
        partial_funding_acceptable=_bool_field(
            timeline.get("can_start_with_partial_funding")
        ),
        authorized_in_law=_bool_field(auth.get("authorized_in_law")),
        authorization_citation=(
            _str_field(auth.get("authorized_in_law"))
            if _bool_field(auth.get("authorized_in_law"))
            else ""
        ),
        in_presidential_budget=_bool_field(auth.get("presidential_budget_request")),
        presidential_budget_details=_str_field(
            auth.get("presidential_budget_request")
        ),
        prior_federal_funding=_bool_field(auth.get("prior_funding")),
        prior_funding_details=_str_field(auth.get("prior_funding")),
        derogatory_info=_bool_field(risk.get("derogatory_information_exists")),
        derogatory_info_explanation=_str_field(
            risk.get("derogatory_information_explanation")
        ),
        members_receiving_request=_str_field(
            other.get("other_members_receiving_request")
        ),
    )
    db.add(cpf)
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

@router.post("/cpf-json", response_model=CPFUploadResponse)
async def upload_cpf_json(
    request: StarletteRequest,
    db: Session = Depends(get_db),
):
    """Upload one or more CPF records in the ChatGPT-parsed JSON schema.

    Accepts either a single `cpf_record` object or an array of them.
    Each record should follow the schema with keys:
    metadata, requesting_organization, point_of_contact, project,
    narratives, support, status_and_eligibility, timeline_and_future_funding,
    authorization_and_budget, risk_and_priority, other_offices, compliance, flags.
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
            result = _create_from_cpf_schema(item, db)
            results.append(result)
        except Exception as e:
            db.rollback()
            errors.append(f"Item {i}: {str(e)}")

    return CPFUploadResponse(created=len(results), requests=results, errors=errors)


# ── CSV columns (exact order from spec) ──────────────────

CSV_COLUMNS = [
    "fiscal_year", "requesting_org_name", "entity_type_normalized",
    "entity_type_raw", "org_address", "org_website", "poc_name", "poc_title",
    "poc_phone", "poc_email", "project_name", "project_summary_line",
    "project_purpose", "project_address", "requested_amount",
    "total_project_cost", "total_funding_request", "subcommittee",
    "subcommittee_normalized", "agency", "eligible_account", "stakeholders",
    "new_or_ongoing", "eligible_purpose", "timeline_to_complete",
    "requires_future_federal_funding", "can_start_with_partial_funding",
    "non_federal_cost_share_required", "priority_rank_if_multiple",
    "other_members_receiving_request", "flags",
]


def _cpf_row_from_json(data: dict) -> dict:
    """Build a flat CSV row dict from the cpf_record JSON schema."""
    metadata = data.get("metadata") or {}
    org = data.get("requesting_organization") or {}
    poc = data.get("point_of_contact") or {}
    project = data.get("project") or {}
    support = data.get("support") or {}
    status_elig = data.get("status_and_eligibility") or {}
    timeline = data.get("timeline_and_future_funding") or {}
    auth = data.get("authorization_and_budget") or {}
    risk = data.get("risk_and_priority") or {}
    other = data.get("other_offices") or {}
    flags = data.get("flags") or []

    stakeholders_list = support.get("stakeholders") or []
    stakeholders_str = (
        "; ".join(stakeholders_list)
        if isinstance(stakeholders_list, list)
        else _str_field(stakeholders_list)
    )
    flags_str = (
        "; ".join(flags) if isinstance(flags, list) else _str_field(flags)
    )

    return {
        "fiscal_year": _get(metadata, "fiscal_year", default=""),
        "requesting_org_name": _str_field(org.get("name")),
        "entity_type_normalized": _str_field(org.get("entity_type_normalized")),
        "entity_type_raw": _str_field(org.get("entity_type_raw")),
        "org_address": _str_field(org.get("address")),
        "org_website": _str_field(org.get("website")),
        "poc_name": _str_field(poc.get("name")),
        "poc_title": _str_field(poc.get("title")),
        "poc_phone": _str_field(poc.get("phone")),
        "poc_email": _str_field(poc.get("email")),
        "project_name": _str_field(project.get("project_name")),
        "project_summary_line": _str_field(project.get("project_summary_line")),
        "project_purpose": _str_field(project.get("purpose")),
        "project_address": _str_field(project.get("project_address")),
        "requested_amount": _str_field(project.get("requested_amount")),
        "total_project_cost": _str_field(project.get("total_project_cost")),
        "total_funding_request": _str_field(project.get("total_funding_request")),
        "subcommittee": _str_field(project.get("subcommittee")),
        "subcommittee_normalized": _str_field(project.get("subcommittee_normalized")),
        "agency": _str_field(project.get("agency")),
        "eligible_account": _str_field(project.get("eligible_account")),
        "stakeholders": stakeholders_str,
        "new_or_ongoing": _str_field(status_elig.get("new_or_ongoing")),
        "eligible_purpose": _str_field(status_elig.get("eligible_purpose")),
        "timeline_to_complete": _str_field(timeline.get("timeline_to_complete")),
        "requires_future_federal_funding": _str_field(
            timeline.get("requires_future_federal_funding")
        ),
        "can_start_with_partial_funding": _str_field(
            timeline.get("can_start_with_partial_funding")
        ),
        "non_federal_cost_share_required": _str_field(
            auth.get("non_federal_cost_share_required")
        ),
        "priority_rank_if_multiple": _str_field(
            risk.get("priority_rank_if_multiple")
        ),
        "other_members_receiving_request": _str_field(
            other.get("other_members_receiving_request")
        ),
        "flags": flags_str,
    }


@router.post("/cpf-csv")
async def export_cpf_csv(request: StarletteRequest):
    """Convert one or more cpf_record JSON objects to CSV (does not save to DB).

    Returns a downloadable CSV file with columns in the specified order.
    """
    payload = await request.json()
    items = payload if isinstance(payload, list) else [payload]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for item in items:
        if isinstance(item, dict):
            writer.writerow(_cpf_row_from_json(item))

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cpf_records.csv"},
    )
