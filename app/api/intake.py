"""
Bulk intake endpoint for ChatGPT-parsed request data.

Accepts two formats:
  1. Structured JSON (single object or array) — the ChatGPT-parsed format with
     nested sections like requesting_organization, project, narratives, etc.
  2. Plain text with key:value pairs, bullet points, numbered lists, or
     markdown formatting. Multiple requests separated by "---" or blank lines.
"""
import json
import re
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Request, CPFDetails, NdaaDetails, EligibleAccount
from app.services.docx_parser import map_subcommittee
from app.api.upload import _best_eligible_account_match
from app.api.prog_lang_upload import _create_from_prog_lang_schema
from app.api.cpf_upload import _create_from_cpf_schema

router = APIRouter()


def _strip_markdown_json(text: str) -> str:
    """Strip markdown code fences and surrounding prose from ChatGPT output."""
    cleaned = text.strip()
    # Remove ```json ... ``` or ``` ... ``` wrappers
    cleaned = re.sub(r"^```(?:json|JSON|js)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?\s*```\s*$", "", cleaned)
    cleaned = cleaned.strip()
    # If there's still non-JSON text before the first { or [, strip it
    if not cleaned.startswith("{") and not cleaned.startswith("["):
        first_brace = re.search(r"[\[{]", cleaned)
        if first_brace:
            cleaned = cleaned[first_brace.start():]
    # If there's trailing text after the last } or ], strip it
    if not cleaned.endswith("}") and not cleaned.endswith("]"):
        last_brace = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if last_brace > -1:
            cleaned = cleaned[: last_brace + 1]
    return cleaned


class TextIntakeRequest(BaseModel):
    text: str


class IntakeResultItem(BaseModel):
    id: int
    title: str
    request_type: str
    subcommittee: str
    organization: str
    amount: Optional[int] = None
    status: str


class TextIntakeResult(BaseModel):
    created: int
    requests: list[IntakeResultItem]
    errors: list[str]


# ── Amount parsing ────────────────────────────────────────

def _parse_amount(value: Any) -> Optional[int]:
    """Parse dollar amounts from int, float, or string ($1,500,000 / $1.5M / 650000)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    cleaned = str(value).strip()
    if not cleaned:
        return None

    # Shorthand: $1.5M, $650K, $2B
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

def _parse_entity_type(raw: str) -> Optional[str]:
    v = (raw or "").lower()
    if "nonprofit" in v or "501" in v or "non-profit" in v:
        return "nonprofit_501c3"
    if "tribal" in v:
        return "state_local_tribal_government"
    if any(kw in v for kw in ("city", "county", "state", "local", "government", "municipal")):
        return "state_local_tribal_government"
    if "public" in v:
        return "public_entity"
    if "university" in v or "college" in v or "higher ed" in v:
        return "public_entity"
    return None


# ── Request type detection ────────────────────────────────

def _parse_request_type(value: str) -> str:
    v = (value or "").lower()
    if "language" in v:
        return "language"
    if "programmatic" in v:
        return "programmatic"
    if "ndaa" in v:
        return "ndaa"
    return "cpf"


# ═══════════════════════════════════════════════════════════
# FORMAT 1: Structured JSON (ChatGPT-parsed)
# ═══════════════════════════════════════════════════════════

def _safe_get(obj: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts."""
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current if current is not None else default


def _detect_json_schema(data: dict) -> str:
    """Detect which JSON schema variant was used.

    Returns:
        "ndaa"       - NDAA schema (has ndaa-specific fields like hasc_subcommittee, funding_agency, etc.)
        "prog_lang"  - programmatic/language schema (has request_details or bill_details)
        "cpf"        - CPF nested schema (has project + requesting_organization, or narratives/support/compliance)
        "cpf_flat"   - CPF flat schema (top-level project_name, requesting_entity, requested_amount, etc.)
        "generic"    - fallback to generic intake parsing
    """
    metadata = data.get("metadata") or {}
    portal = data.get("submission_portal_fields") or {}
    request_type = (portal.get("request_type") or metadata.get("request_type") or "").lower()
    top_type = (data.get("request_type") or "").lower()
    doc_title = (metadata.get("document_title") or "").lower()

    # NDAA detection: explicit type or NDAA-specific fields
    if "ndaa" in request_type or "ndaa" in top_type or "ndaa" in doc_title:
        return "ndaa"
    if "national defense" in request_type or "national defense" in top_type or "national defense" in doc_title:
        return "ndaa"
    # NDAA-specific field signals
    ndaa_signals = sum([
        bool(data.get("hasc_subcommittee")),
        bool(data.get("funding_agency")),
        bool(data.get("budget_account")),
        bool(data.get("official_project_name")),
        bool(data.get("proposed_bill_language")),
        bool(data.get("proposed_report_language")),
        bool(data.get("military_value")),
        bool(data.get("program_element")),
        bool(data.get("funded_in_pb") is not None and data.get("funded_in_pb") is not False or data.get("funded_in_pb") is True),
        bool(data.get("unfunded_priority_list")),
        bool(data.get("met_with_congressman")),
        bool(data.get("poc_is_lobbyist") is not None and "poc_is_lobbyist" in data),
    ])
    if ndaa_signals >= 3:
        return "ndaa"

    # Programmatic/language schema: has request_details, bill_details,
    # submission_portal_fields, committee_submission, or
    # top-level "organization" (not "requesting_organization")
    if data.get("request_details") or data.get("bill_details"):
        return "prog_lang"
    if data.get("submission_portal_fields") or data.get("committee_submission"):
        return "prog_lang"
    if request_type in ("programmatic", "language"):
        return "prog_lang"
    # Flat prog/lang: top-level request_type field says programmatic or language
    if top_type in ("programmatic", "language") or "language" in top_type or "programmatic" in top_type:
        return "prog_lang"
    # Has proposal_text or appropriations_bill or committee — prog/lang signals
    if data.get("proposal_text") or data.get("appropriations_bill"):
        return "prog_lang"
    if data.get("organization") and not data.get("requesting_organization"):
        # "organization" key is prog_lang; CPF uses "requesting_organization"
        if data.get("justification") or data.get("prior_history"):
            return "prog_lang"

    # CPF nested schema: has project + requesting_organization or CPF-specific sections
    if data.get("project") and (data.get("requesting_organization") or data.get("narratives")):
        return "cpf"
    if data.get("compliance") or data.get("flags") is not None:
        return "cpf"

    # CPF flat schema: top-level project fields with CPF indicators
    # (project_name + requested_amount, or requesting_entity, or account/subcommittee + amount)
    cpf_flat_signals = sum([
        bool(data.get("project_name")),
        bool(data.get("requesting_entity")),
        bool(data.get("requested_amount")),
        bool(data.get("total_project_cost")),
        bool(data.get("project_purpose") or data.get("project_description")),
        bool(data.get("public_benefit")),
        bool(data.get("account")),
        bool(data.get("entity_type")),
        bool(data.get("project_location")),
        bool(data.get("members_submitted_to")),
    ])
    if cpf_flat_signals >= 3:
        return "cpf_flat"

    return "generic"


def _create_from_flat_cpf(data: dict, db: Session) -> dict:
    """Create a Request + CPFDetails from a flat CPF JSON structure.

    Handles JSON where CPF fields are at the top level (not nested under
    project/requesting_organization/narratives sections).
    """
    # Point of contact may be nested or flat
    poc = data.get("point_of_contact") or {}
    poc_name = poc.get("name") if isinstance(poc, dict) else ""
    poc_email = poc.get("email") if isinstance(poc, dict) else ""
    poc_phone = poc.get("phone") if isinstance(poc, dict) else ""

    # Timeline may be nested or a string
    timeline_raw = data.get("timeline") or {}
    if isinstance(timeline_raw, dict):
        timeline_str = f"{timeline_raw.get('start', '')} - {timeline_raw.get('end', '')}".strip(" -")
    else:
        timeline_str = str(timeline_raw)

    # Prior funding may be nested
    prior_funding_raw = data.get("prior_funding") or {}
    has_prior_funding = False
    prior_funding_details = ""
    if isinstance(prior_funding_raw, dict):
        has_prior_funding = bool(prior_funding_raw.get("federal") or prior_funding_raw.get("details"))
        details = prior_funding_raw.get("details") or []
        if isinstance(details, list):
            prior_funding_details = "; ".join(str(d) for d in details)
        else:
            prior_funding_details = str(details)
        fed = prior_funding_raw.get("federal")
        non_fed = prior_funding_raw.get("non_federal")
        if fed or non_fed:
            amounts = []
            if fed:
                amounts.append(f"Federal: ${fed:,}" if isinstance(fed, (int, float)) else f"Federal: {fed}")
            if non_fed:
                amounts.append(f"Non-Federal: ${non_fed:,}" if isinstance(non_fed, (int, float)) else f"Non-Federal: {non_fed}")
            prior_funding_details = "; ".join(amounts) + ("; " + prior_funding_details if prior_funding_details else "")
    elif prior_funding_raw:
        has_prior_funding = True
        prior_funding_details = str(prior_funding_raw)

    # Members submitted to
    members_raw = data.get("members_submitted_to") or []
    if isinstance(members_raw, list):
        members_str = "; ".join(str(m) for m in members_raw)
    else:
        members_str = str(members_raw)

    # Subcommittee
    raw_sub = data.get("subcommittee") or data.get("bill") or data.get("appropriations_bill") or ""
    subcommittee = map_subcommittee(raw_sub)
    if not subcommittee:
        subcommittee = map_subcommittee(data.get("agency") or "")
    if not subcommittee:
        subcommittee = "agriculture"

    title = data.get("project_name") or data.get("requesting_entity") or "Imported CPF Request"
    amount = _parse_amount(data.get("requested_amount"))
    total_cost = _parse_amount(data.get("total_project_cost"))
    entity_type = _parse_entity_type(data.get("entity_type") or "")

    # Fiscal year
    fy_raw = data.get("fiscal_year") or "2027"
    try:
        fy = int(re.sub(r"[^0-9]", "", str(fy_raw))[-4:]) if fy_raw else 2027
    except (ValueError, IndexError):
        fy = 2027

    description = data.get("project_purpose") or data.get("project_description") or ""

    request = Request(
        fiscal_year=fy,
        request_type="cpf",
        subcommittee=subcommittee,
        status="submitted",
        title=title,
        description=description,
        requester_name=poc_name or data.get("requester_name") or "",
        requester_email=poc_email or data.get("requester_email") or "",
        requester_phone=poc_phone or data.get("requester_phone") or "",
        requester_organization=data.get("requesting_entity") or data.get("entity_name") or "",
        requested_amount=amount,
        agency=data.get("agency") or "",
        priority_rank=str(data.get("priority_rank")) if data.get("priority_rank") else None,
    )
    db.add(request)
    db.flush()

    # Eligible account matching
    cpf_account_id = None
    eligible_raw = data.get("account") or data.get("eligible_account") or ""
    agency_raw = data.get("agency") or ""
    if eligible_raw or agency_raw:
        accounts = db.query(EligibleAccount).filter(
            EligibleAccount.subcommittee == subcommittee
        ).all()
        cpf_account_id = _best_eligible_account_match(accounts, eligible_raw, agency_raw)

    cpf = CPFDetails(
        request_id=request.id,
        cpf_account_id=cpf_account_id,
        tx11_nexus=True,
        tx11_nexus_explanation=data.get("priority_reason") or "",
        entity_type=entity_type,
        entity_name=data.get("requesting_entity") or data.get("entity_name") or "",
        entity_address=data.get("address") or "",
        project_name=title,
        project_address=data.get("project_location") or "",
        project_description=description,
        requested_amount=amount,
        total_project_cost=total_cost,
        cost_share_required=bool(data.get("cost_share_required")),
        cost_share_explanation="",
        public_benefit_justification=data.get("public_benefit") or "",
        tx11_priority_justification=data.get("priority_reason") or "",
        stakeholders_support="",
        eligibility_citations="",
        timeline=timeline_str,
        future_federal_funding=bool(data.get("future_federal_funding_required")),
        partial_funding_acceptable=bool(data.get("scalable_with_partial_funding")),
        authorized_in_law=bool(
            data.get("authorization_status")
            and str(data.get("authorization_status")).lower() not in ("n/a", "no", "")
        ),
        authorization_citation=str(data.get("authorization_status") or ""),
        in_presidential_budget=False,
        presidential_budget_details="",
        prior_federal_funding=has_prior_funding,
        prior_funding_details=prior_funding_details,
        derogatory_info=bool(data.get("derogatory_information")),
        derogatory_info_explanation="",
        members_receiving_request=members_str,
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


def _create_from_flat_ndaa(data: dict, db: Session) -> dict:
    """Create a Request + NdaaDetails from a flat NDAA JSON structure."""
    title = (
        data.get("official_project_name")
        or data.get("company_organization")
        or data.get("title")
        or data.get("program_name")
        or "NDAA Request"
    )

    # HASC subcommittee mapping — NDAA is always defense
    subcommittee = "defense"

    amount = _parse_amount(
        data.get("additional_funding_amount")
        or data.get("requested_amount")
        or data.get("fy26_bill_amount")
    )

    request = Request(
        fiscal_year=data.get("fiscal_year") or 2027,
        request_type="ndaa",
        subcommittee=subcommittee,
        status="submitted",
        title=title,
        description=data.get("program_description") or data.get("justification") or "",
        requester_name=data.get("poc_name") or "",
        requester_email=data.get("email") or "",
        requester_phone=data.get("phone") or "",
        requester_organization=data.get("company_organization") or "",
        requested_amount=amount,
    )
    db.add(request)
    db.flush()

    ndaa = NdaaDetails(
        request_id=request.id,
        company_organization=data.get("company_organization") or "",
        address=data.get("address") or "",
        city=data.get("city") or "",
        state=data.get("state") or "TX",
        zip_code=data.get("zip_code") or "",
        poc_name=data.get("poc_name") or "",
        poc_is_lobbyist=bool(data.get("poc_is_lobbyist")),
        lobbyist_organization=data.get("lobbyist_organization") or "",
        phone=data.get("phone") or "",
        email=data.get("email") or "",
        met_with_congressman=data.get("met_with_congressman") or "",
        meeting_date=data.get("meeting_date") or "",
        multiple_requests=bool(data.get("multiple_requests")),
        request_priority=data.get("request_priority") or "",
        official_project_name=data.get("official_project_name") or "",
        funding_agency=data.get("funding_agency") or data.get("agency") or "",
        budget_account=data.get("budget_account") or "",
        sub_account_1=data.get("sub_account_1") or "",
        sub_account_2=data.get("sub_account_2") or "",
        line_title=data.get("line_title") or "",
        line_number=data.get("line_number") or "",
        hasc_subcommittee=data.get("hasc_subcommittee") or "",
        funded_in_pb=bool(data.get("funded_in_pb")),
        program_element=data.get("program_element") or "",
        additional_funding_amount=_parse_amount(data.get("additional_funding_amount")),
        is_scalable=bool(data.get("is_scalable")),
        scalable_amount=_parse_amount(data.get("scalable_amount")),
        fy26_bill_amount=_parse_amount(data.get("fy26_bill_amount")),
        unfunded_priority_list=bool(data.get("unfunded_priority_list")),
        unfunded_ranking=data.get("unfunded_ranking") or "",
        unfunded_amount=_parse_amount(data.get("unfunded_amount")),
        proposed_bill_language=data.get("proposed_bill_language") or "",
        proposed_report_language=data.get("proposed_report_language") or "",
        items_of_special_interest=data.get("items_of_special_interest") or "",
        justification=data.get("justification") or "",
        program_description=data.get("program_description") or "",
        military_value=data.get("military_value") or "",
        tx11_impact=data.get("tx11_impact") or "",
        partners=data.get("partners") or "",
        other_offices_engaged=data.get("other_offices_engaged") or "",
        committee_staff_engaged=data.get("committee_staff_engaged") or "",
        additional_notes=data.get("additional_notes") or "",
    )
    db.add(ndaa)
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


def _create_from_json(data: dict, db: Session) -> dict:
    """Create a request from the ChatGPT-parsed JSON structure.

    Auto-detects the schema variant (CPF, programmatic/language, NDAA, or generic)
    and routes to the appropriate handler.
    """
    schema = _detect_json_schema(data)

    if schema == "ndaa":
        return _create_from_flat_ndaa(data, db)
    if schema == "prog_lang":
        return _create_from_prog_lang_schema(data, db)
    if schema == "cpf":
        return _create_from_cpf_schema(data, db)
    if schema == "cpf_flat":
        return _create_from_flat_cpf(data, db)

    # Generic / fallback: use the original intake logic
    project = data.get("project", {}) or {}
    org = data.get("requesting_organization", {}) or {}
    poc = data.get("point_of_contact", {}) or {}
    narratives = data.get("narratives", {}) or {}
    status_elig = data.get("status_and_eligibility", {}) or {}
    timeline = data.get("timeline_and_future_funding", {}) or {}
    auth = data.get("authorization_and_budget", {}) or {}
    risk = data.get("risk_and_priority", {}) or {}
    other = data.get("other_offices", {}) or {}
    support = data.get("support", {}) or {}
    compliance = data.get("compliance", {}) or {}
    metadata = data.get("metadata", {}) or {}

    # Determine request type from metadata or document_title
    doc_title = _safe_get(metadata, "document_title", default="")
    request_type = "cpf"  # default
    if "ndaa" in doc_title.lower():
        request_type = "ndaa"
    elif "programmatic" in doc_title.lower():
        request_type = "programmatic"
    elif "language" in doc_title.lower():
        request_type = "language"

    # Subcommittee: try normalized, then raw, then agency fallback
    raw_sub = project.get("subcommittee_normalized") or project.get("subcommittee") or ""
    subcommittee = map_subcommittee(raw_sub)
    if not subcommittee:
        subcommittee = map_subcommittee(project.get("agency") or "")
    if not subcommittee:
        subcommittee = "agriculture"

    title = project.get("project_name") or project.get("project_summary_line") or "Imported Request"
    amount = _parse_amount(project.get("requested_amount") or project.get("total_funding_request"))
    total_cost = _parse_amount(project.get("total_project_cost"))
    fy = _safe_get(metadata, "fiscal_year", default=2027)

    # Build description from purpose / summary
    description = project.get("purpose") or project.get("project_summary_line") or ""

    # Entity type
    entity_type_raw = org.get("entity_type_raw") or org.get("entity_type_normalized") or ""
    entity_type = _parse_entity_type(entity_type_raw)

    request = Request(
        fiscal_year=fy or 2027,
        request_type=request_type,
        subcommittee=subcommittee,
        status="submitted",
        title=title,
        description=description,
        requester_name=poc.get("name") or "",
        requester_email=poc.get("email") or "",
        requester_phone=poc.get("phone") or "",
        requester_organization=org.get("name") or "",
        requested_amount=amount,
        agency=project.get("agency") or "",
        priority_rank=_safe_get(risk, "priority_rank_if_multiple") or None,
    )
    db.add(request)
    db.flush()

    # Create CPF details if CPF type
    if request_type == "cpf":
        # Try to match eligible account
        cpf_account_id = None
        eligible_raw = project.get("eligible_account") or ""
        agency_raw = project.get("agency") or ""
        if eligible_raw or agency_raw:
            accounts = db.query(EligibleAccount).filter(
                EligibleAccount.subcommittee == subcommittee
            ).all()
            cpf_account_id = _best_eligible_account_match(accounts, eligible_raw, agency_raw)

        # Stakeholders
        stakeholders_list = support.get("stakeholders") or []
        stakeholders_str = "; ".join(stakeholders_list) if isinstance(stakeholders_list, list) else str(stakeholders_list)

        # Cost share
        cost_share_required = auth.get("non_federal_cost_share_required", False)
        cost_share_explanation = auth.get("cost_share_explanation") or ""

        # Authorization
        auth_in_law_raw = auth.get("authorized_in_law") or ""
        authorized_in_law = bool(auth_in_law_raw and auth_in_law_raw.lower() not in ("n/a", "no", ""))

        # Derogatory info
        derog = risk.get("derogatory_information_exists", False)
        derog_explanation = risk.get("derogatory_information_explanation") or ""

        # Citations
        citations = status_elig.get("citations") or []
        citation_texts = [c.get("citation_text", "") for c in citations if isinstance(c, dict)]
        eligibility_justification = status_elig.get("eligibility_justification") or ""
        if citation_texts:
            eligibility_justification += " " + "; ".join(citation_texts)

        cpf = CPFDetails(
            request_id=request.id,
            cpf_account_id=cpf_account_id,
            tx11_nexus=compliance.get("tx11_based_claimed", True),
            tx11_nexus_explanation=narratives.get("district_priority_justification") or "",
            entity_type=entity_type,
            entity_name=org.get("name") or "",
            entity_address=org.get("address") or "",
            project_name=title,
            project_address=project.get("project_address") or "",
            project_description=description,
            requested_amount=amount,
            total_project_cost=total_cost,
            cost_share_required=cost_share_required,
            cost_share_explanation=cost_share_explanation,
            public_benefit_justification=narratives.get("public_benefit_and_taxpayer_rationale") or "",
            tx11_priority_justification=narratives.get("district_priority_justification") or "",
            stakeholders_support=stakeholders_str,
            eligibility_citations=eligibility_justification.strip(),
            timeline=timeline.get("timeline_to_complete") or "",
            future_federal_funding=timeline.get("requires_future_federal_funding", False),
            partial_funding_acceptable=timeline.get("can_start_with_partial_funding", False),
            authorized_in_law=authorized_in_law,
            authorization_citation=auth_in_law_raw if authorized_in_law else "",
            in_presidential_budget=bool(
                auth.get("presidential_budget_request")
                and auth.get("presidential_budget_request", "").lower() not in ("n/a", "no", "")
            ),
            presidential_budget_details=auth.get("presidential_budget_request") or "",
            prior_federal_funding=bool(
                auth.get("prior_funding")
                and auth.get("prior_funding", "").lower() not in ("n/a", "no", "")
            ),
            prior_funding_details=auth.get("prior_funding") or "",
            derogatory_info=derog,
            derogatory_info_explanation=derog_explanation,
            members_receiving_request=other.get("other_members_receiving_request") or "",
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


# ═══════════════════════════════════════════════════════════
# FORMAT 2: Plain text parsing
# ═══════════════════════════════════════════════════════════

# Aliases for key:value text parsing
_FIELD_ALIASES = {
    "title": ["project name", "project title", "title", "project", "name of project", "request title"],
    "subcommittee": ["subcommittee", "sub-committee", "committee", "appropriations subcommittee",
                      "appropriations bill", "bill"],
    "request_type": ["request type", "type", "category", "funding type"],
    "amount": ["requested amount", "amount", "funding amount", "request amount",
               "amount requested", "funding requested", "federal funding", "federal amount"],
    "organization": ["organization", "entity", "entity name", "org", "applicant",
                      "requesting organization", "requesting entity", "recipient",
                      "recipient organization", "grantee"],
    "requester_name": ["submitter", "requester", "contact", "contact name", "submitted by",
                        "point of contact", "poc", "requestor", "name"],
    "email": ["email", "email address", "contact email", "e-mail"],
    "phone": ["phone", "phone number", "contact phone", "telephone"],
    "description": ["description", "purpose", "purpose of project", "project description",
                     "summary", "project summary", "overview", "justification", "details"],
    "agency": ["agency", "federal agency", "department"],
    "program_name": ["program", "program name", "federal program"],
    "entity_type": ["entity type", "organization type", "org type", "applicant type"],
    "project_address": ["project address", "project location", "location", "address"],
    "total_project_cost": ["total cost", "total project cost", "project cost"],
}

_ALIAS_MAP: dict[str, str] = {}
for _canonical, _aliases in _FIELD_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_MAP[_alias] = _canonical


def _normalize_key(raw: str) -> str:
    cleaned = re.sub(r"\*+", "", raw).strip().lower().rstrip(":")
    if cleaned in _ALIAS_MAP:
        return _ALIAS_MAP[cleaned]
    for alias, canonical in sorted(_ALIAS_MAP.items(), key=lambda x: -len(x[0])):
        if alias in cleaned:
            return canonical
    return cleaned


def _split_requests(text: str) -> list[str]:
    """Split text into individual request blocks."""
    if re.search(r"\n-{3,}\n|\n={3,}\n", text):
        blocks = re.split(r"\n-{3,}\n|\n={3,}\n", text)
        blocks = [b.strip() for b in blocks if b.strip()]
        if len(blocks) > 1:
            return blocks

    header_pattern = r"(?:^|\n)(?:#{1,3}\s*)?(?:Request\s*#?\s*\d+[:\s])"
    if len(re.findall(header_pattern, text, re.IGNORECASE)) > 1:
        parts = re.split(header_pattern, text, flags=re.IGNORECASE)
        blocks = [p.strip() for p in parts if p.strip()]
        if len(blocks) > 1:
            return blocks

    blocks = re.split(r"\n\s*\n\s*\n", text)
    blocks = [b.strip() for b in blocks if b.strip()]
    if len(blocks) > 1:
        kv_blocks = [b for b in blocks if re.search(r"[A-Za-z]+\s*:", b)]
        if len(kv_blocks) > 1:
            return kv_blocks

    return [text.strip()]


def _parse_block(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue

        line = re.sub(r"^\s*[-*]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)]\s+", "", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)

        if ":" not in line:
            if "description" in fields:
                fields["description"] += " " + line
            elif fields:
                last_key = list(fields.keys())[-1]
                fields[last_key] += " " + line
            continue

        idx = line.index(":")
        raw_key = line[:idx].strip()
        raw_value = line[idx + 1:].strip()
        if not raw_key or not raw_value:
            continue

        canonical = _normalize_key(raw_key)
        if canonical in fields and not raw_value:
            continue
        fields[canonical] = raw_value

    return fields


def _create_from_text_fields(fields: dict[str, str], db: Session, block_num: int = 1) -> dict:
    """Create a request from parsed key:value text fields."""
    request_type = _parse_request_type(fields.get("request_type", ""))

    raw_sub = fields.get("subcommittee", "")
    subcommittee = map_subcommittee(raw_sub)
    if not subcommittee:
        for fallback in ["agency", "program_name", "description", "title"]:
            subcommittee = map_subcommittee(fields.get(fallback, ""))
            if subcommittee:
                break
    if not subcommittee:
        subcommittee = "agriculture"

    title = fields.get("title") or fields.get("program_name") or f"Imported Request #{block_num}"
    amount = _parse_amount(fields.get("amount", ""))
    total_cost = _parse_amount(fields.get("total_project_cost", ""))

    request = Request(
        fiscal_year=2027,
        request_type=request_type,
        subcommittee=subcommittee,
        status="submitted",
        title=title,
        description=fields.get("description") or "",
        requester_name=fields.get("requester_name") or "",
        requester_email=fields.get("email") or "",
        requester_phone=fields.get("phone") or "",
        requester_organization=fields.get("organization") or "",
        requested_amount=amount,
        program_name=fields.get("program_name") or "",
        agency=fields.get("agency") or "",
    )
    db.add(request)
    db.flush()

    if request_type == "cpf":
        entity_type = _parse_entity_type(fields.get("entity_type", "") or fields.get("organization", ""))
        cpf_account_id = None
        eligible_raw = fields.get("eligible_account", "")
        agency_raw = fields.get("agency", "")
        if eligible_raw or agency_raw:
            accounts = db.query(EligibleAccount).filter(
                EligibleAccount.subcommittee == subcommittee
            ).all()
            cpf_account_id = _best_eligible_account_match(accounts, eligible_raw, agency_raw)

        cpf = CPFDetails(
            request_id=request.id,
            cpf_account_id=cpf_account_id,
            tx11_nexus=True,
            entity_type=entity_type,
            entity_name=fields.get("organization") or "",
            project_name=title,
            project_address=fields.get("project_address") or "",
            project_description=fields.get("description") or "",
            requested_amount=amount,
            total_project_cost=total_cost,
            public_benefit_justification=fields.get("description") or "",
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


# ═══════════════════════════════════════════════════════════
# Endpoint
# ═══════════════════════════════════════════════════════════

@router.post("/text", response_model=TextIntakeResult)
def bulk_text_intake(
    payload: TextIntakeRequest,
    db: Session = Depends(get_db),
):
    """Parse ChatGPT output into one or more appropriations requests.

    Accepts either:
      - **Structured JSON**: Single object or JSON array of ChatGPT-parsed requests
        with nested fields (requesting_organization, project, narratives, etc.)
      - **Plain text**: Key:value pairs, bullet points, numbered lists, or markdown.
        Multiple requests separated by `---` lines, double blank lines, or numbered
        headers (Request 1, Request 2, ...).

    The subcommittee is automatically detected from the text and mapped to the
    correct value.
    """
    raw = payload.text.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    results: list[dict] = []
    errors: list[str] = []

    # Try JSON first — strip markdown code blocks if present
    cleaned = _strip_markdown_json(raw)
    if cleaned.startswith("{") or cleaned.startswith("["):
        try:
            parsed = json.loads(cleaned)
            items = parsed if isinstance(parsed, list) else [parsed]

            for i, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    errors.append(f"Item {i}: expected a JSON object")
                    continue
                try:
                    result = _create_from_json(item, db)
                    results.append(result)
                except Exception as e:
                    errors.append(f"Item {i}: {str(e)}")

            return TextIntakeResult(created=len(results), requests=results, errors=errors)
        except json.JSONDecodeError:
            pass  # Fall through to text parsing

    # Plain text parsing
    blocks = _split_requests(raw)

    for i, block in enumerate(blocks, start=1):
        fields = _parse_block(block)
        if not fields:
            errors.append(f"Block {i}: no parseable fields found")
            continue

        try:
            result = _create_from_text_fields(fields, db, block_num=i)
            results.append(result)
        except Exception as e:
            errors.append(f"Block {i}: {str(e)}")

    return TextIntakeResult(created=len(results), requests=results, errors=errors)
