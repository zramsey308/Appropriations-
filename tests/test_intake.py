"""Tests for the ChatGPT intake endpoint (JSON and plain text)."""
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── JSON intake (ChatGPT structured format) ────────────────

SAMPLE_CPF_JSON = {
    "metadata": {
        "fiscal_year": 2027,
        "document_title": "FY'27 Community Project Funding (CPF) Requests",
    },
    "requesting_organization": {
        "name": "City of San Angelo, Texas",
        "entity_type_normalized": "local_government",
        "entity_type_raw": "State, Local, or Tribal Government",
        "address": "72 West College Avenue San Angelo, TX 76903",
    },
    "point_of_contact": {
        "name": "Travis Griffith",
        "title": "Chief of Police",
        "phone": "325-227-0237",
        "email": "travis.griffith@sanangelo.gov",
    },
    "project": {
        "project_name": "San Angelo Regional Public Safety Training Complex",
        "purpose": "Design and construct a regional Public Safety Training and Emergency Operations Center.",
        "project_address": "3501 US-67, San Angelo, TX 76905",
        "requested_amount": 32063824,
        "total_project_cost": 32063824,
        "subcommittee": "Transportation, Housing, and Urban Development",
        "subcommittee_normalized": "thud",
        "agency": "Department of Housing and Urban Development",
        "eligible_account": "Economic Development Initiatives (EDI)",
    },
    "narratives": {
        "public_benefit_and_taxpayer_rationale": "Centralizes fragmented public safety training resources.",
        "district_priority_justification": "Only purpose-built regional complex serving Concho Valley.",
    },
    "support": {
        "stakeholders": ["Senator Charles Perry", "Lt. Gen Ronnie Hawkins"],
    },
    "status_and_eligibility": {
        "eligible_purpose": True,
        "eligibility_justification": "Eligible under HUD EDI.",
        "citations": [{"citation_text": "42 U.S.C. 5301", "citation_type": "usc"}],
    },
    "timeline_and_future_funding": {
        "timeline_to_complete": "36 months",
        "requires_future_federal_funding": False,
        "can_start_with_partial_funding": True,
    },
    "authorization_and_budget": {
        "authorized_in_law": "N/A",
        "presidential_budget_request": "N/A",
        "prior_funding": "N/A",
        "non_federal_cost_share_required": False,
        "cost_share_explanation": "No statutory match required.",
    },
    "risk_and_priority": {
        "derogatory_information_exists": False,
        "priority_rank_if_multiple": "#1",
    },
    "compliance": {
        "tx11_based_claimed": True,
    },
}


def test_json_intake_single():
    resp = client.post("/api/intake/text", json={"text": json.dumps(SAMPLE_CPF_JSON)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert len(body["requests"]) == 1
    r = body["requests"][0]
    assert r["title"] == "San Angelo Regional Public Safety Training Complex"
    assert r["request_type"] == "cpf"
    assert r["subcommittee"] == "transportation_hud"
    assert r["organization"] == "City of San Angelo, Texas"
    assert r["amount"] == 32063824


def test_json_intake_maps_subcommittee_from_thud():
    data = {**SAMPLE_CPF_JSON}
    data["project"] = {**data["project"], "subcommittee": "Transportation, HUD", "subcommittee_normalized": "thud"}
    resp = client.post("/api/intake/text", json={"text": json.dumps(data)})
    assert resp.json()["requests"][0]["subcommittee"] == "transportation_hud"


def test_json_intake_maps_subcommittee_energy_water():
    data = {**SAMPLE_CPF_JSON}
    data["project"] = {**data["project"], "subcommittee": "Energy and Water Development", "subcommittee_normalized": None}
    resp = client.post("/api/intake/text", json={"text": json.dumps(data)})
    assert resp.json()["requests"][0]["subcommittee"] == "energy_water"


def test_json_intake_maps_subcommittee_defense():
    data = {**SAMPLE_CPF_JSON}
    data["project"] = {**data["project"], "subcommittee": "Defense", "subcommittee_normalized": None}
    resp = client.post("/api/intake/text", json={"text": json.dumps(data)})
    assert resp.json()["requests"][0]["subcommittee"] == "defense"


def test_json_intake_maps_subcommittee_cjs():
    data = {**SAMPLE_CPF_JSON}
    data["project"] = {**data["project"], "subcommittee": "Commerce, Justice, Science", "subcommittee_normalized": None}
    resp = client.post("/api/intake/text", json={"text": json.dumps(data)})
    assert resp.json()["requests"][0]["subcommittee"] == "commerce_justice_science"


def test_json_intake_maps_subcommittee_labor_hhs():
    data = {**SAMPLE_CPF_JSON}
    data["project"] = {**data["project"], "subcommittee": "Labor, HHS, Education", "subcommittee_normalized": None}
    resp = client.post("/api/intake/text", json={"text": json.dumps(data)})
    assert resp.json()["requests"][0]["subcommittee"] == "labor_hhs_education"


def test_json_intake_creates_cpf_details():
    resp = client.post("/api/intake/text", json={"text": json.dumps(SAMPLE_CPF_JSON)})
    rid = resp.json()["requests"][0]["id"]
    cpf = client.get(f"/api/requests/{rid}/cpf").json()
    assert cpf["entity_name"] == "City of San Angelo, Texas"
    assert cpf["project_name"] == "San Angelo Regional Public Safety Training Complex"
    assert cpf["requested_amount"] == 32063824
    assert cpf["tx11_nexus"] is True
    assert "Centralizes" in cpf["public_benefit_justification"]
    assert cpf["cost_share_required"] is False
    assert "36 months" in cpf["timeline"]
    assert "Senator Charles Perry" in cpf["stakeholders_support"]


def test_json_intake_array():
    """Submit an array of two JSON requests."""
    data2 = {**SAMPLE_CPF_JSON}
    data2["project"] = {**data2["project"], "project_name": "Second Project", "requested_amount": 1000000}
    data2["requesting_organization"] = {**data2["requesting_organization"], "name": "City of Odessa"}

    resp = client.post("/api/intake/text", json={"text": json.dumps([SAMPLE_CPF_JSON, data2])})
    body = resp.json()
    assert body["created"] == 2
    titles = {r["title"] for r in body["requests"]}
    assert "San Angelo Regional Public Safety Training Complex" in titles
    assert "Second Project" in titles


# ── Plain text intake ──────────────────────────────────────

def test_text_intake_simple():
    text = """Project Name: Midland Water Treatment Upgrade
Subcommittee: Energy and Water
Requested Amount: $3,000,000
Organization: City of Midland
Submitter: John Smith
Request Type: CPF
Description: Upgrade water treatment facilities."""
    resp = client.post("/api/intake/text", json={"text": text})
    body = resp.json()
    assert body["created"] == 1
    r = body["requests"][0]
    assert r["title"] == "Midland Water Treatment Upgrade"
    assert r["subcommittee"] == "energy_water"
    assert r["amount"] == 3000000


def test_text_intake_bullet_format():
    text = """- **Project Name:** Rural Broadband Expansion
- **Subcommittee:** Commerce, Justice, Science
- **Requested Amount:** $1.5M
- **Organization:** West Texas Telecom
- **Request Type:** CPF
- **Description:** Expand broadband coverage."""
    resp = client.post("/api/intake/text", json={"text": text})
    body = resp.json()
    assert body["created"] == 1
    assert body["requests"][0]["amount"] == 1500000
    assert body["requests"][0]["subcommittee"] == "commerce_justice_science"


def test_text_intake_multiple_separated_by_dashes():
    text = """Project Name: Project Alpha
Subcommittee: Defense
Requested Amount: $500,000
Organization: Alpha Corp
Request Type: CPF

---

Project Name: Project Beta
Subcommittee: Agriculture
Requested Amount: $200,000
Organization: Beta Farm Co
Request Type: CPF"""
    resp = client.post("/api/intake/text", json={"text": text})
    body = resp.json()
    assert body["created"] == 2
    subs = {r["subcommittee"] for r in body["requests"]}
    assert "defense" in subs
    assert "agriculture" in subs


def test_text_intake_shorthand_amounts():
    text = """Project Name: Big Project
Subcommittee: Defense
Requested Amount: $2.5M
Organization: Test Corp
Request Type: CPF"""
    resp = client.post("/api/intake/text", json={"text": text})
    assert resp.json()["requests"][0]["amount"] == 2500000


def test_text_intake_empty():
    resp = client.post("/api/intake/text", json={"text": ""})
    assert resp.status_code == 400


def test_text_intake_unparseable():
    resp = client.post("/api/intake/text", json={"text": "just some random text with no fields"})
    body = resp.json()
    assert body["created"] == 0
    assert len(body["errors"]) > 0
