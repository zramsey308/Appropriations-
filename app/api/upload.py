"""
Upload endpoint for parsing Word documents into requests.
"""
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.docx_parser import parse_docx, map_subcommittee
from app.models import Request, CPFDetails, NdaaDetails, EligibleAccount

router = APIRouter()


def _normalized_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    words = [w for w in cleaned.split() if w not in {"and", "the", "of", "for", "services", "service", "program", "account", "grants", "grant"}]
    return set(words)


def _is_meaningful_text(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    known_labels = {
        "project name:", "project name", "purpose of project:", "subcommittee:", "agency:",
        "eligible account (see list above):", "eligible account:", "name:", "title:", "phone #:", "email address:"
    }
    if text in known_labels:
        return False

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and all(line.endswith(":") for line in lines):
        return False

    label_hits = sum(1 for line in lines if line in known_labels)
    if label_hits >= 2:
        return False

    return True


def _best_eligible_account_match(accounts: list[EligibleAccount], eligible_account_raw: str, agency_raw: str) -> int | None:
    target_tokens = _normalized_tokens(eligible_account_raw)
    agency_tokens = _normalized_tokens(agency_raw)

    best_id = None
    best_score = 0.0
    for account in accounts:
        account_tokens = _normalized_tokens(account.account_name)
        account_agency_tokens = _normalized_tokens(account.agency)

        overlap = len(target_tokens & account_tokens)
        union = len(target_tokens | account_tokens) or 1
        score = overlap / union

        # agency bonus helps when account label is abbreviated in form (e.g., STRS)
        if agency_tokens and account_agency_tokens and len(agency_tokens & account_agency_tokens) > 0:
            score += 0.2

        if "strs" in (eligible_account_raw or "").lower() and "scientific" in account_tokens and "technical" in account_tokens:
            score += 0.5

        if score > best_score:
            best_score = score
            best_id = account.id

    # keep threshold modest: forms often contain abbreviated account labels
    return best_id if best_score >= 0.2 else None


@router.post("/docx")
async def upload_docx(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a Word document and automatically create a request from it.
    Supports CPF, Programmatic/Language, and NDAA forms.
    """
    if not file.filename.endswith((".docx", ".doc")):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        fields = parse_docx(contents)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Failed to parse document")
        raise HTTPException(status_code=400, detail=f"Failed to parse document: {str(e)}")

    doc_type = fields.pop("_doc_type", None)
    if not doc_type:
        raise HTTPException(
            status_code=400,
            detail="Could not determine document type. Please upload a CPF, Programmatic/Language, or NDAA request form (.docx).",
        )

    if doc_type == "cpf":
        return _create_cpf_request(fields, db)
    elif doc_type == "programmatic":
        return _create_programmatic_request(fields, db)
    elif doc_type == "ndaa":
        return _create_ndaa_request(fields, db)


def _create_cpf_request(fields: dict, db: Session) -> dict:
    """Create a CPF request from parsed fields."""
    meaningful_values = [
        _is_meaningful_text(fields.get("entity_name")),
        _is_meaningful_text(fields.get("project_name")),
        _is_meaningful_text(fields.get("project_description")),
        bool(fields.get("requested_amount")),
        _is_meaningful_text(fields.get("subcommittee")),
    ]
    if not any(meaningful_values):
        raise HTTPException(status_code=400, detail="CPF form appears blank or unfilled. Please provide completed form fields.")

    subcommittee = map_subcommittee(fields.get("subcommittee", "")) or "agriculture"

    cpf_account_id = None
    eligible_account_raw = (fields.get("eligible_account") or "").strip()
    agency_raw = (fields.get("agency") or "").strip()
    if eligible_account_raw or agency_raw:
        accounts = db.query(EligibleAccount).filter(EligibleAccount.subcommittee == subcommittee).all()
        cpf_account_id = _best_eligible_account_match(accounts, eligible_account_raw, agency_raw)

    request = Request(
        fiscal_year=2027,
        request_type="cpf",
        subcommittee=subcommittee,
        status="submitted",
        title=fields.get("project_name") or fields.get("entity_name") or "CPF Request",
        description=fields.get("project_description") or "",
        requester_name=fields.get("requester_name") or "",
        requester_email=fields.get("requester_email") or "",
        requester_phone=fields.get("requester_phone") or "",
        requester_organization=fields.get("entity_name") or "",
        requested_amount=fields.get("requested_amount"),
    )
    db.add(request)
    db.flush()

    cpf = CPFDetails(
        request_id=request.id,
        cpf_account_id=cpf_account_id,
        tx11_nexus=True,
        tx11_nexus_explanation=fields.get("tx11_priority") or "",
        entity_type=fields.get("entity_type"),
        entity_name=fields.get("entity_name") or "",
        entity_address=fields.get("entity_address") or "",
        project_name=fields.get("project_name") or "",
        project_address=fields.get("project_address") or "",
        project_description=fields.get("project_description") or "",
        requested_amount=fields.get("requested_amount"),
        total_project_cost=fields.get("total_project_cost"),
        cost_share_amount=None,
        cost_share_required=bool(fields.get("cost_share")),
        cost_share_explanation=fields.get("cost_share") or "",
        public_benefit_justification=fields.get("public_benefit") or "",
        tx11_priority_justification=fields.get("tx11_priority") or "",
        stakeholders_support=fields.get("stakeholders") or "",
        eligibility_citations=fields.get("eligibility_justification") or "",
        timeline=fields.get("timeline") or "",
        future_federal_funding=bool(fields.get("future_federal_funding")),
        future_federal_funding_explanation=fields.get("future_federal_funding") or "",
        partial_funding_acceptable=bool(fields.get("partial_funding")),
        partial_funding_explanation=fields.get("partial_funding") or "",
        authorized_in_law=bool(fields.get("authorized_in_law") and fields.get("authorized_in_law").lower() not in ("n/a", "no", "")),
        authorization_citation=fields.get("authorized_in_law") or "",
        in_presidential_budget=bool(fields.get("presidential_budget")),
        presidential_budget_details=fields.get("presidential_budget") or "",
        prior_federal_funding=bool(fields.get("prior_funding")),
        prior_funding_details=fields.get("prior_funding") or "",
        derogatory_info=bool(fields.get("derogatory_info") and fields.get("derogatory_info").lower() not in ("no", "n/a", "")),
        derogatory_info_explanation=fields.get("derogatory_info") or "",
        members_receiving_request=fields.get("members_receiving") or "",
    )
    db.add(cpf)
    db.commit()
    db.refresh(request)

    return {
        "id": request.id,
        "doc_type": "cpf",
        "title": request.title,
        "organization": request.requester_organization,
        "amount": request.requested_amount,
        "subcommittee": request.subcommittee,
        "status": "submitted",
        "message": f"CPF request created successfully (#{request.id})",
        "fields_extracted": {k: v for k, v in fields.items() if v},
    }


def _create_programmatic_request(fields: dict, db: Session) -> dict:
    """Create a Programmatic or Language request from parsed fields."""
    # Determine if this is programmatic or language based on filled fields
    has_program = bool(fields.get("program_name"))
    has_language = bool(fields.get("proposed_language"))

    if has_language and not has_program:
        request_type = "language"
    else:
        request_type = "programmatic"

    # Map the appropriations bill to subcommittee
    raw_bill = fields.get("appropriations_bill", "")
    subcommittee = map_subcommittee(raw_bill) or "agriculture"

    requester_name = " ".join(filter(None, [fields.get("first_name"), fields.get("last_name")]))

    request = Request(
        fiscal_year=2027,
        request_type=request_type,
        subcommittee=subcommittee,
        status="submitted",
        title=fields.get("title") or "Programmatic Request",
        description=fields.get("request_description") or fields.get("problem_statement") or "",
        requester_name=requester_name,
        requester_email=fields.get("email") or "",
        requester_phone=fields.get("business_phone") or fields.get("cell_phone") or "",
        requester_organization=fields.get("organization_name") or "",
        program_name=fields.get("program_name") or "",
        requested_amount=fields.get("last_fy_amount") or fields.get("presidents_budget_amount"),
        programmatic_justification=fields.get("goals_outcomes") or "",
        bill_section=fields.get("bill_section") or "",
        proposed_language=fields.get("proposed_language") or "",
        language_justification=fields.get("problem_statement") or "",
        priority_rank=fields.get("priority") or None,
        problem_statement=fields.get("problem_statement") or None,
        goals_outcomes=fields.get("goals_outcomes") or None,
        other_members=fields.get("other_members") or None,
        prior_year_submission=bool(fields.get("prior_submissions")),
        prior_year_details=fields.get("prior_submissions") or None,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    return {
        "id": request.id,
        "doc_type": request_type,
        "title": request.title,
        "organization": request.requester_organization,
        "amount": request.requested_amount,
        "subcommittee": request.subcommittee,
        "status": "submitted",
        "message": f"{request_type.capitalize()} request created successfully (#{request.id})",
        "fields_extracted": {k: v for k, v in fields.items() if v},
    }


def _create_ndaa_request(fields: dict, db: Session) -> dict:
    """Create an NDAA request from parsed fields."""
    title = fields.get("official_project_name") or fields.get("company_organization") or "NDAA Request"

    request = Request(
        fiscal_year=2027,
        request_type="ndaa",
        subcommittee="defense",
        status="submitted",
        title=title,
        description=fields.get("program_description") or fields.get("justification") or "",
        requester_name=fields.get("poc_name") or "",
        requester_email=fields.get("email") or "",
        requester_phone=fields.get("phone") or "",
        requester_organization=fields.get("company_organization") or "",
        requested_amount=fields.get("additional_funding_amount"),
    )
    db.add(request)
    db.flush()

    ndaa = NdaaDetails(
        request_id=request.id,
        company_organization=fields.get("company_organization") or "",
        address=fields.get("address") or "",
        city=fields.get("city") or "",
        state=fields.get("state") or "TX",
        zip_code=fields.get("zip_code") or "",
        poc_name=fields.get("poc_name") or "",
        poc_is_lobbyist=fields.get("poc_is_lobbyist", False),
        lobbyist_organization=fields.get("lobbyist_organization") or "",
        phone=fields.get("phone") or "",
        email=fields.get("email") or "",
        met_with_congressman=fields.get("met_with_congressman") or "",
        meeting_date=fields.get("meeting_date") or "",
        multiple_requests=fields.get("multiple_requests", False),
        request_priority=fields.get("request_priority") or "",
        official_project_name=fields.get("official_project_name") or "",
        funding_agency=fields.get("funding_agency") or "",
        budget_account=fields.get("budget_account") or "",
        sub_account_1=fields.get("sub_account_1") or "",
        sub_account_2=fields.get("sub_account_2") or "",
        line_title=fields.get("line_title") or "",
        line_number=fields.get("line_number") or "",
        hasc_subcommittee=fields.get("hasc_subcommittee") or "",
        funded_in_pb=fields.get("funded_in_pb", False),
        program_element=fields.get("program_element") or "",
        additional_funding_amount=fields.get("additional_funding_amount"),
        is_scalable=fields.get("is_scalable", False),
        scalable_amount=fields.get("scalable_amount"),
        fy26_bill_amount=fields.get("fy26_bill_amount"),
        unfunded_priority_list=fields.get("unfunded_priority_list", False),
        unfunded_ranking=fields.get("unfunded_ranking") or "",
        unfunded_amount=fields.get("unfunded_amount"),
        proposed_bill_language=fields.get("proposed_bill_language") or "",
        proposed_report_language=fields.get("proposed_report_language") or "",
        items_of_special_interest=fields.get("items_of_special_interest") or "",
        justification=fields.get("justification") or "",
        program_description=fields.get("program_description") or "",
        military_value=fields.get("military_value") or "",
        tx11_impact=fields.get("tx11_impact") or "",
        partners=fields.get("partners") or "",
        other_offices_engaged=fields.get("other_offices_engaged") or "",
        committee_staff_engaged=fields.get("committee_staff_engaged") or "",
        additional_notes=fields.get("additional_notes") or "",
    )
    db.add(ndaa)
    db.commit()
    db.refresh(request)

    return {
        "id": request.id,
        "doc_type": "ndaa",
        "title": request.title,
        "organization": request.requester_organization,
        "amount": request.requested_amount,
        "subcommittee": request.subcommittee,
        "status": "submitted",
        "message": f"NDAA request created successfully (#{request.id})",
        "fields_extracted": {k: v for k, v in fields.items() if v},
    }
