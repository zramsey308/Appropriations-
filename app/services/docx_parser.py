"""
Word document parser for appropriations request forms.
Handles three document types: CPF, Programmatic/Language, and NDAA.
"""
import re
import logging
from typing import Optional

from docx import Document

logger = logging.getLogger(__name__)


def parse_docx(file_bytes: bytes) -> dict:
    """
    Parse a Word document and return structured data.

    Returns a dict with:
        - doc_type: "cpf", "programmatic", or "ndaa"
        - fields: dict of extracted field values
    """
    from io import BytesIO
    doc = Document(BytesIO(file_bytes))

    # Extract all text from paragraphs and tables
    all_text = _extract_all_text(doc)
    full_text = "\n".join(all_text)

    # Detect document type
    doc_type = _detect_type(full_text)

    if doc_type == "cpf":
        fields = _parse_cpf(all_text, full_text)
    elif doc_type == "programmatic":
        fields = _parse_programmatic(all_text, full_text)
    elif doc_type == "ndaa":
        fields = _parse_ndaa(all_text, full_text)
    else:
        raise ValueError("Could not determine document type. Expected CPF, Programmatic/Language, or NDAA form.")

    fields["_doc_type"] = doc_type
    return fields


def _extract_all_text(doc: Document) -> list[str]:
    """Extract text from paragraphs, tables, and content controls (SDTs).

    Real Word forms use Structured Document Tags (SDTs / content controls)
    at both the body level (wrapping tables) and cell level (fillable fields).
    This function walks the XML tree directly to capture all text.
    """
    from docx.oxml.ns import qn

    lines = []

    def _get_element_text(el) -> str:
        """Extract all text from an XML element, including SDT content."""
        texts = []
        for node in el.iter():
            if node.tag == qn('w:t') and node.text:
                texts.append(node.text)
        return "".join(texts).strip()

    def _process_table(tbl_element):
        """Extract text from a table element row by row."""
        for tr in tbl_element.findall(qn('w:tr')):
            cells = tr.findall(qn('w:tc'))
            row_texts = [_get_element_text(tc) for tc in cells]
            combined = "\t".join(t for t in row_texts if t)
            if combined:
                lines.append(combined)

    def _process_body_element(element):
        """Process a single body-level element (paragraph, table, or SDT)."""
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            text = _get_element_text(element)
            if text:
                lines.append(text)

        elif tag == "tbl":
            _process_table(element)

        elif tag == "sdt":
            # Content control — recurse into sdtContent to find paragraphs/tables
            sdt_content = element.find(qn('w:sdtContent'))
            if sdt_content is not None:
                for child in sdt_content:
                    _process_body_element(child)

    for element in doc.element.body:
        _process_body_element(element)

    return lines


def _detect_type(full_text: str) -> Optional[str]:
    """Detect the document type from content."""
    text_lower = full_text.lower()

    if "community project funding" in text_lower or "cpf request" in text_lower:
        return "cpf"
    elif "national defense authorization" in text_lower or "ndaa" in text_lower or "budgetary legislative proposal" in text_lower or "hasc subcommittee" in text_lower:
        return "ndaa"
    elif "programmatic" in text_lower or "section: 1 (organization information)" in text_lower or "section 3: request details" in text_lower:
        return "programmatic"

    # Fallback heuristics for forms without exact header text
    if ("request form" in text_lower and "project name" in text_lower and "entity" in text_lower):
        return "cpf"
    if ("request form" in text_lower or "appropriation" in text_lower) and "project name" in text_lower:
        return "cpf"
    if "organization name" in text_lower and ("program name" in text_lower or "appropriations bill" in text_lower):
        return "programmatic"

    return None


_PLACEHOLDER_TEXTS = {
    "click here to enter text.",
    "click here to enter text",
    "click or tap here to enter text.",
    "click or tap here to enter text",
    "type here",
    "enter text here",
    "[enter text]",
    "",
}

# Section headers that should never be treated as field values
_SECTION_HEADERS = {
    "section 1", "section 2", "section 3", "section 4", "section 5",
    "section: 1", "section: 2", "section: 3", "section: 4",
    "section 1 (organization information)",
    "section: 1 (organization information)",
    "section: 2 (contact information)",
    "section 2 (contact information)",
    "section 3: request details",
    "section: 3 (request details)",
    "organization information",
    "contact information",
    "request details",
}


def _is_placeholder(text: str) -> bool:
    """Check if text is a Word form placeholder or section header."""
    normalized = text.strip().lower()
    if normalized in _PLACEHOLDER_TEXTS:
        return True
    # Check for section headers
    for header in _SECTION_HEADERS:
        if normalized == header or normalized.startswith(header + " "):
            return True
    return False


def _is_section_header(text: str) -> bool:
    """Check if text is a section header that should not be a field value."""
    normalized = text.strip().lower()
    for header in _SECTION_HEADERS:
        if normalized == header or normalized.startswith(header):
            return True
    if re.match(r"^section\s*:?\s*\d", normalized):
        return True
    return False


def _find_value(lines: list[str], label: str, stop_labels: list[str] = None) -> str:
    """
    Find the value for a given label in the document lines.
    Looks for the label, then returns subsequent non-label text.
    """
    label_lower = label.lower().strip().rstrip(":")
    found = False
    values = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check if this line contains or matches the label
        if not found:
            line_lower = line_stripped.lower()
            if label_lower in line_lower:
                # Check if value is on the same line after the label
                # Try splitting on tab first (table cells)
                parts = line_stripped.split("\t")
                if len(parts) > 1:
                    # Value might be in a subsequent cell
                    for i, part in enumerate(parts):
                        if label_lower in part.lower():
                            remaining = "\t".join(parts[i+1:]).strip()
                            if remaining and not _is_placeholder(remaining):
                                return remaining
                            break

                # Try splitting on colon
                colon_idx = line_lower.find(label_lower) + len(label_lower)
                remaining = line_stripped[colon_idx:].strip().lstrip(":")
                if remaining and not _is_placeholder(remaining):
                    return remaining

                found = True
                continue

        if found:
            # Check if we hit a stop label
            if stop_labels:
                line_lower = line_stripped.lower()
                for sl in stop_labels:
                    if sl.lower() in line_lower:
                        return "\n".join(values).strip()

            # Check if it looks like a new label (ends with colon or starts with number.)
            if (line_stripped.endswith(":") and len(line_stripped) < 80) or re.match(r"^\d+[\.\)]\s", line_stripped):
                if values:
                    return "\n".join(values).strip()
                # Might be a sub-label, continue
                continue

            text = line_stripped
            if not _is_placeholder(text):
                values.append(text)
            elif values:
                # Found placeholder after collecting some values, stop
                return "\n".join(values).strip()

            # Only collect a few lines max for single-value fields
            if len(values) >= 1 and not stop_labels:
                return "\n".join(values).strip()

    return "\n".join(values).strip()


def _find_multiline_value(lines: list[str], label: str, stop_labels: list[str]) -> str:
    """Find a multi-line value between a label and the next stop label."""
    label_lower = label.lower().strip()
    found = False
    values = []

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            if found and values:
                values.append("")
            continue

        line_lower = line_stripped.lower()

        if not found:
            if label_lower in line_lower:
                # Check for value on same line after label
                colon_idx = line_lower.find(label_lower) + len(label_lower)
                remaining = line_stripped[colon_idx:].strip().lstrip(":")
                if remaining and not _is_placeholder(remaining):
                    values.append(remaining)
                found = True
                continue
        else:
            # Check stop labels
            for sl in stop_labels:
                if sl.lower() in line_lower:
                    return "\n".join(values).strip()

            if not _is_placeholder(line_stripped):
                values.append(line_stripped)

    return "\n".join(values).strip()


def _find_value_after_anchor(lines: list[str], anchor: str, label: str, stop_labels: list[str] = None) -> str:
    """Find a value by first locating an anchor line, then searching for a label after it."""
    anchor_lower = anchor.lower().strip()
    start_idx = 0
    for idx, line in enumerate(lines):
        if anchor_lower in line.lower():
            start_idx = idx
            break
    return _find_value(lines[start_idx:], label, stop_labels)


def _parse_amount(text: str) -> Optional[int]:
    """Parse a dollar amount from text."""
    if not text:
        return None
    # Remove $, commas, spaces
    cleaned = re.sub(r'[,$\s]', '', text)
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def _line_after_label(full_text: str, label_regex: str) -> str:
    """Extract text after a label on the same line from full_text."""
    match = re.search(rf"(?im)^\s*{label_regex}\s*:\s*(.+)$", full_text)
    return match.group(1).strip() if match else ""


def _clean_field_value(value: str) -> str:
    """Normalize parser artifacts from table/label extraction."""
    if not value:
        return value
    cleaned = value.strip()
    cleaned = re.sub(r"^/?(?:of\s+Project|/Entity|Entity|#)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\(See list above\)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    label_only_values = {"project name:", "project name", "purpose of project:", "purpose of project", "subcommittee:", "subcommittee", "agency:", "agency", "name:", "title:", "phone #:", "email address:", "project information:", "point of contact for request:", "eligible account (see list above):", "eligible account:"}
    if cleaned.lower() in label_only_values:
        return ""
    return cleaned


def _project_name_from_project_info(full_text: str) -> str:
    """Derive a project name from 'Project Information' line when Project Name is blank."""
    match = re.search(r"(?im)^\s*Project Information\s*:\s*(.+)$", full_text)
    if not match:
        return ""
    text = match.group(1).strip()
    # common pattern: "$650,000 to expand ..."
    text = re.sub(r"^\$?[\d,]+\s*(?:to\s+)?", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return ""
    return text[:180]


def _parse_cpf(lines: list[str], full_text: str) -> dict:
    """Parse a CPF request form."""
    fields = {}

    # Organization info
    fields["entity_name"] = _find_value(lines, "Name of Requesting Organization")
    fields["entity_address"] = _find_value(lines, "Address of Organization")
    fields["website"] = _find_value(lines, "Website")

    # Entity type detection - prefer explicit selected value near "Type of Entity"
    type_line = _find_value(lines, "Type of Entity")
    entity_text = f"{type_line}\n{full_text}".lower()
    if "state" in entity_text and "government" in entity_text:
        fields["entity_type"] = "state_government"
    elif "local" in entity_text and "government" in entity_text:
        fields["entity_type"] = "local_government"
    elif "tribal" in entity_text and "government" in entity_text:
        fields["entity_type"] = "tribal_government"
    elif "public entity" in entity_text:
        fields["entity_type"] = "public_entity"
    elif "501(c" in entity_text or "nonprofit" in entity_text:
        fields["entity_type"] = "nonprofit_501c3"

    # Contact info
    fields["requester_name"] = _find_value_after_anchor(lines, "Point of Contact for Request", "Name:", ["Title:"])
    fields["requester_title"] = _find_value_after_anchor(lines, "Point of Contact for Request", "Title:", ["Phone"])
    fields["requester_phone"] = _find_value_after_anchor(lines, "Point of Contact for Request", "Phone", ["Email"])
    fields["requester_email"] = _find_value_after_anchor(lines, "Point of Contact for Request", "Email Address:", ["Project"])

    # Project info
    fields["project_name"] = _find_value(lines, "Project Name:", ["Purpose"])
    fields["project_description"] = _find_multiline_value(lines, "Purpose of Project:", ["Postal Address"])
    fields["project_address"] = _find_value(lines, "Postal Address", ["Requested"])
    requested_text = _find_value(lines, "Requested FY", ["Subcommittee"])
    fields["requested_amount"] = _parse_amount(requested_text)
    if fields["requested_amount"] is None:
        requested_match = re.search(r"requested\s+fy[^\n:]*:\s*\$?([\d,]+)", full_text, flags=re.IGNORECASE)
        if requested_match:
            fields["requested_amount"] = _parse_amount(requested_match.group(1))

    fields["subcommittee"] = _find_value(lines, "Subcommittee:", ["Agency"])
    if not fields["subcommittee"]:
        subcommittee_match = re.search(r"subcommittee\s*:\s*([^\n]+)", full_text, flags=re.IGNORECASE)
        fields["subcommittee"] = subcommittee_match.group(1).strip() if subcommittee_match else ""
    fields["agency"] = _find_value(lines, "Agency:", ["Eligible Account"])
    fields["eligible_account"] = _find_value(lines, "Eligible Account", ["Supporting"])

    # Targeted line-based fallbacks for common CPF forms
    fields["entity_name"] = fields["entity_name"] or _line_after_label(full_text, r"Name of Requesting Organization/Entity")
    fields["entity_address"] = fields["entity_address"] or _line_after_label(full_text, r"Address of Organization")
    fields["website"] = fields["website"] or _line_after_label(full_text, r"Website")
    fields["requester_name"] = fields["requester_name"] or _line_after_label(full_text, r"Name")
    fields["requester_title"] = fields["requester_title"] or _line_after_label(full_text, r"Title")
    fields["requester_phone"] = fields["requester_phone"] or _line_after_label(full_text, r"Phone\s*#?")
    fields["requester_email"] = fields["requester_email"] or _line_after_label(full_text, r"Email Address")
    fields["project_name"] = fields["project_name"] or _line_after_label(full_text, r"Project Name")
    if not fields["project_name"]:
        fields["project_name"] = _project_name_from_project_info(full_text)
    fields["project_address"] = fields["project_address"] or _line_after_label(full_text, r"Postal Address of Project")
    fields["subcommittee"] = fields["subcommittee"] or _line_after_label(full_text, r"Subcommittee")
    if (not fields["agency"]) or ("\n" in fields["agency"]) or ("address of organization" in fields["agency"].lower()):
        fields["agency"] = _line_after_label(full_text, r"Agency")
    fields["eligible_account"] = fields["eligible_account"] or _line_after_label(full_text, r"Eligible Account(?:\s*\(See list above\))?")

    # Clean obvious extraction artifacts
    for key in ["entity_name", "entity_address", "website", "requester_name", "requester_title", "requester_phone", "requester_email", "project_name", "project_address", "subcommittee", "agency", "eligible_account"]:
        fields[key] = _clean_field_value(fields.get(key, ""))

    # Suppress common label bleed-through in blank/partial forms
    invalid_starts = ("purpose of project", "project name", "point of contact", "requested fy", "subcommittee", "agency", "project information")
    if fields["project_name"].lower().startswith(invalid_starts):
        fields["project_name"] = ""
    if fields["requester_name"].lower().startswith(("title", "phone", "email")):
        fields["requester_name"] = ""

    if not fields["project_name"]:
        fields["project_name"] = _project_name_from_project_info(full_text)
    if fields.get("project_description", "").strip().lower() in {"purpose of project:", "project name:"}:
        fields["project_description"] = ""
    if not fields["project_name"] and fields.get("project_description"):
        fields["project_name"] = fields["project_description"].split(".")[0][:180].strip()

    # Supporting documentation (19 questions)
    fields["public_benefit"] = _find_multiline_value(lines, "benefit the public", ["2."])
    fields["total_funding_request"] = _parse_amount(_find_multiline_value(lines, "2.\tTotal funding request", ["3."]))
    fields["total_project_cost"] = _parse_amount(_find_multiline_value(lines, "3.\tTotal project cost", ["4."]))
    fields["tx11_priority"] = _find_multiline_value(lines, "priority for the people of Texas", ["5."])
    fields["stakeholders"] = _find_multiline_value(lines, "stakeholders that support", ["6."])
    fields["funding_breakdown"] = _find_multiline_value(lines, "breakdown here of how", ["7."])
    fields["new_or_ongoing"] = _find_multiline_value(lines, "new or ongoing", ["8."])
    fields["eligible_purpose"] = _find_multiline_value(lines, "eligible purpose", ["9."])
    fields["eligibility_justification"] = _find_multiline_value(lines, "justify the project", ["10."])
    fields["timeline"] = _find_multiline_value(lines, "timeline of completion", ["11."])
    fields["future_federal_funding"] = _find_multiline_value(lines, "additional federal dollars", ["12."])
    fields["partial_funding"] = _find_multiline_value(lines, "limited capacity", ["13."])
    fields["authorized_in_law"] = _find_multiline_value(lines, "currently authorized in law", ["14."])
    fields["presidential_budget"] = _find_multiline_value(lines, "presidential budget request", ["15."])
    fields["prior_funding"] = _find_multiline_value(lines, "received any funding in the past", ["16."])
    fields["cost_share"] = _find_multiline_value(lines, "non-federal cost share", ["17."])
    fields["derogatory_info"] = _find_multiline_value(lines, "derogatory information", ["18."])
    fields["priority_ranking"] = _find_value(lines, "rank this request", ["19."])
    fields["members_receiving"] = _find_multiline_value(lines, "Members of both the United States", [])

    return fields


def _clean_programmatic_field(value: str, max_len: int = 500) -> str:
    """Clean a programmatic field: remove section headers, placeholders, and truncate."""
    if not value:
        return ""
    cleaned = value.strip()
    # Remove section header lines
    cleaned_lines = []
    for line in cleaned.split("\n"):
        stripped = line.strip()
        if _is_section_header(stripped):
            continue
        if stripped.lower().startswith("please ") and len(stripped) < 100 and ":" in stripped:
            continue  # Skip instruction lines like "Please provide a short title..."
        cleaned_lines.append(stripped)
    cleaned = "\n".join(cleaned_lines).strip()
    # Truncate excessively long values (likely a parser bleed-through)
    if len(cleaned) > max_len:
        # Try to find a natural break point
        truncated = cleaned[:max_len]
        last_period = truncated.rfind(".")
        if last_period > max_len // 2:
            truncated = truncated[:last_period + 1]
        cleaned = truncated
    return cleaned


def _parse_programmatic(lines: list[str], full_text: str) -> dict:
    """Parse a Programmatic/Language request form."""
    fields = {}

    # Section 1 - Organization
    fields["organization_name"] = _find_value(lines, "Organization Name:")
    fields["street_address"] = _find_value(lines, "Street Address:")
    fields["city"] = _find_value(lines, "City:")
    fields["state"] = _find_value(lines, "State:")
    fields["zip_code"] = _find_value(lines, "Zip Code:")
    fields["phone"] = _find_value(lines, "Phone Number:")
    fields["website"] = _find_value(lines, "Website:")
    fields["entity_type"] = _find_value(lines, "Type of Entity:")
    fields["co_sponsors"] = _find_value(lines, "Co-sponsoring Organizations:")

    # Section 2 - Contact
    fields["first_name"] = _find_value(lines, "First Name:")
    fields["last_name"] = _find_value(lines, "Last Name:")
    fields["contact_address"] = _find_value(lines, "Street Address:", ["City:"])
    fields["contact_city"] = _find_value(lines, "City:", ["State:"])
    fields["business_phone"] = _find_value(lines, "Business Phone Number:")
    fields["cell_phone"] = _find_value(lines, "Cell Phone Number:")
    fields["email"] = _find_value(lines, "E-mail Address:")

    # Section 3 - Request Details
    fields["title"] = _find_multiline_value(lines, "short title to your request", ["2)", "Please list"])
    fields["priority"] = _find_value(lines, "priority of this request", ["3)", "Problem"])
    fields["problem_statement"] = _find_multiline_value(lines, "Problem/Issue Statement", ["4)", "Request description"])
    fields["request_description"] = _find_multiline_value(lines, "Request description", ["5)", "goals and expected"])
    fields["goals_outcomes"] = _find_multiline_value(lines, "goals and expected outcomes", ["6)", "Program Name"])

    # Programmatic fields
    fields["program_name"] = _find_value(lines, "Program Name and Agency")
    fields["last_fy_amount"] = _parse_amount(_find_value(lines, "Amount included last fiscal year"))
    fields["presidents_budget_amount"] = _parse_amount(_find_value(lines, "Amount included in the President"))

    # Language fields
    fields["proposed_language"] = _find_multiline_value(lines, "requesting bill, report", ["8)", "appropriations bill"])

    # Bill info
    fields["appropriations_bill"] = _find_value(lines, "appropriations bill and section")
    fields["bill_section"] = _find_value(lines, "Section:")
    fields["other_members"] = _find_multiline_value(lines, "other Representatives or Senators", ["10)", "submitted in prior"])
    fields["prior_submissions"] = _find_multiline_value(lines, "submitted in prior years", [])

    # Clean all text fields to remove section headers and truncate excessively long values
    for key in ["organization_name", "first_name", "last_name", "email",
                "business_phone", "cell_phone", "phone"]:
        val = fields.get(key, "")
        if _is_section_header(val):
            fields[key] = ""
        elif len(val) > 255:
            fields[key] = val[:255]

    fields["title"] = _clean_programmatic_field(fields.get("title", ""), max_len=500)
    fields["problem_statement"] = _clean_programmatic_field(fields.get("problem_statement", ""), max_len=5000)
    fields["request_description"] = _clean_programmatic_field(fields.get("request_description", ""), max_len=5000)
    fields["goals_outcomes"] = _clean_programmatic_field(fields.get("goals_outcomes", ""), max_len=5000)
    fields["proposed_language"] = _clean_programmatic_field(fields.get("proposed_language", ""), max_len=5000)
    fields["other_members"] = _clean_programmatic_field(fields.get("other_members", ""), max_len=2000)
    fields["prior_submissions"] = _clean_programmatic_field(fields.get("prior_submissions", ""), max_len=2000)

    return fields


def _parse_ndaa(lines: list[str], full_text: str) -> dict:
    """Parse an NDAA request form."""
    fields = {}

    # Section I - General Information
    fields["company_organization"] = _find_value(lines, "Company/Organization:", ["Address:"])
    fields["address"] = _find_value(lines, "Address:", ["City:"])
    fields["city"] = _find_value(lines, "City:", ["State:"])
    fields["state"] = _find_value(lines, "State:", ["Zip:"])
    fields["zip_code"] = _find_value(lines, "Zip:", ["Point of Contact"])
    fields["poc_name"] = _find_value(lines, "Point of Contact", ["Is POC"])
    fields["poc_is_lobbyist"] = "yes" in _find_value(lines, "Is POC a lobbyist", ["Lobbyist"]).lower() if _find_value(lines, "Is POC a lobbyist", ["Lobbyist"]) else False
    fields["lobbyist_organization"] = _find_value(lines, "Lobbyist Company", ["Phone:"])
    fields["phone"] = _find_value(lines, "Phone:", ["E-mail:"])
    fields["email"] = _find_value(lines, "E-mail:", ["Did you meet"])
    fields["met_with_congressman"] = _find_value(lines, "Did you meet with Congressman", ["Date of meeting"])
    fields["meeting_date"] = _find_value(lines, "Date of meeting", ["Is your Company"])
    fields["multiple_requests"] = "yes" in _find_value(lines, "multiple requests", ["If Yes"]).lower() if _find_value(lines, "multiple requests", ["If Yes"]) else False
    fields["request_priority"] = _find_value(lines, "this request's priority", ["Section II"])

    # Section II - Budgetary Legislative Proposal
    fields["official_project_name"] = _find_value(lines, "Official Project Name:", ["Proposed Funding"])
    fields["funding_agency"] = _find_value(lines, "Proposed Funding Agency:", ["Budget Account"])
    fields["budget_account"] = _find_value(lines, "Budget Account:", ["Sub Account"])
    fields["sub_account_1"] = _find_value(lines, "Sub Account 1:", ["Sub Account 2"])
    fields["sub_account_2"] = _find_value(lines, "Sub Account 2:", ["Line Title"])
    fields["line_title"] = _find_value(lines, "Line Title:", ["Line Number"])
    fields["line_number"] = _find_value(lines, "Line Number:", ["HASC"])
    fields["hasc_subcommittee"] = _find_value(lines, "HASC Subcommittee:", ["Is"])
    fields["funded_in_pb"] = "yes" in _find_value(lines, "funded in the President", ["Program Element"]).lower() if _find_value(lines, "funded in the President", ["Program Element"]) else False
    fields["program_element"] = _find_value(lines, "Program Element:", ["Additional funding"])
    fields["additional_funding_amount"] = _parse_amount(_find_value(lines, "Additional funding", ["Is funding"]))
    fields["is_scalable"] = "yes" in _find_value(lines, "scalable", ["If Yes"]).lower() if _find_value(lines, "scalable", ["If Yes"]) else False
    fields["scalable_amount"] = _parse_amount(_find_value(lines, "If Yes, amount:", ["Amount included"]))
    fields["fy26_bill_amount"] = _parse_amount(_find_value(lines, "Amount included in the FY26", ["Is the project"]))
    fields["unfunded_priority_list"] = "yes" in _find_value(lines, "Unfunded Priority", ["If Yes"]).lower() if _find_value(lines, "Unfunded Priority", ["If Yes"]) else False
    fields["unfunded_ranking"] = _find_value(lines, "Ranking:", ["Amount:"])
    fields["unfunded_amount"] = _parse_amount(_find_value(lines, "Amount:", ["Section III"]))

    # Section III - Policy Legislative Proposal
    fields["proposed_bill_language"] = _find_multiline_value(lines, "Proposed Bill Language", ["Section IV", "Proposed Report Language"])
    fields["proposed_report_language"] = _find_multiline_value(lines, "Report Language", ["Section IV", "Items of Special Interest"])
    fields["items_of_special_interest"] = _find_multiline_value(lines, "Items of Special Interest", ["Section IV"])

    # Section IV - Proposal Explanation
    fields["justification"] = _find_multiline_value(lines, "Justification statement", ["Please describe"])
    fields["program_description"] = _find_multiline_value(lines, "describe your program/project in no more than three sentences", ["Military value"])
    fields["military_value"] = _find_multiline_value(lines, "Military value", ["Impact for Texas"])
    fields["tx11_impact"] = _find_multiline_value(lines, "Impact for Texas-11", ["Industrial"])
    fields["partners"] = _find_multiline_value(lines, "Industrial, Academic", ["Additional House"])
    fields["other_offices_engaged"] = _find_multiline_value(lines, "Additional House of Representatives", ["Which Professional"])
    fields["committee_staff_engaged"] = _find_multiline_value(lines, "Professional Staff Members", ["Additional notes"])
    fields["additional_notes"] = _find_multiline_value(lines, "Additional notes", [])

    return fields


def map_subcommittee(raw: str) -> Optional[str]:
    """Map raw subcommittee text to enum value."""
    if not raw:
        return None

    raw_lower = raw.lower()
    mapping = {
        "agriculture": "agriculture",
        "commerce": "commerce_justice_science",
        "cjs": "commerce_justice_science",
        "justice": "commerce_justice_science",
        "science": "commerce_justice_science",
        "nasa": "commerce_justice_science",
        "defense": "defense",
        "armed services": "defense",
        "hasc": "defense",
        "ndaa": "defense",
        "national defense": "defense",
        "energy": "energy_water",
        "water": "energy_water",
        "financial": "financial_services",
        "homeland": "homeland_security",
        "interior": "interior_environment",
        "environment": "interior_environment",
        "labor": "labor_hhs_education",
        "hhs": "labor_hhs_education",
        "health": "labor_hhs_education",
        "education": "labor_hhs_education",
        "legislative": "legislative_branch",
        "milcon": "milcon_va",
        "military construction": "milcon_va",
        "veterans": "milcon_va",
        "state": "state_foreign_operations",
        "foreign": "state_foreign_operations",
        "transportation": "transportation_hud",
        "hud": "transportation_hud",
        "housing": "transportation_hud",
    }

    for key, value in mapping.items():
        if key in raw_lower:
            return value

    return None
