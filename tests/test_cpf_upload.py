"""Tests for the CPF JSON schema upload endpoint."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_CPF_RECORD = {
    "metadata": {
        "fiscal_year": 2027,
        "document_title": "CPF Request Form",
        "source_format": "word_or_pasted_text",
        "parsed_utc": "2026-03-01T12:00:00Z",
    },
    "requesting_organization": {
        "name": "City of Arlington",
        "entity_type_normalized": "local_government",
        "entity_type_raw": "City / Local Government",
        "address": "101 W Abram St, Arlington, TX 76010",
        "website": "https://arlingtontx.gov",
    },
    "point_of_contact": {
        "name": "Jane Smith",
        "title": "Grants Manager",
        "phone": "817-555-0100",
        "email": "jsmith@arlingtontx.gov",
    },
    "project": {
        "project_name": "Downtown Transit Hub Expansion",
        "project_summary_line": "Expand the downtown transit hub to serve 10,000 daily riders",
        "purpose": "Improve public transit access in the TX-11 district",
        "project_address": "200 E Abram St, Arlington, TX 76010",
        "requested_amount": "$3,500,000",
        "total_project_cost": "$8,200,000",
        "total_funding_request": "$3,500,000",
        "subcommittee": "Transportation, Housing and Urban Development",
        "subcommittee_normalized": "transportation_hud",
        "agency": "Department of Transportation",
        "eligible_account": "Transit Infrastructure Grants",
        "supporting_documentation_listed": "Letters of support, budget narrative",
    },
    "narratives": {
        "public_benefit_and_taxpayer_rationale": "This project will serve 10,000 daily commuters and reduce traffic congestion.",
        "district_priority_justification": "Top priority for TX-11 residents who rely on public transit.",
        "funding_breakdown": "$3.5M federal, $4.7M local match",
    },
    "support": {
        "stakeholders": ["Arlington Chamber of Commerce", "TxDOT", "Tarrant County"],
        "community_support_evidence_mentioned": "3 letters of support attached",
    },
    "status_and_eligibility": {
        "new_or_ongoing": "New",
        "eligible_purpose_yes_no_raw": "Yes",
        "eligible_purpose": "Transit infrastructure improvement",
        "eligibility_justification": "Eligible under 49 U.S.C. 5309 fixed guideway capital investment grants",
        "citations": [
            {"citation_text": "49 U.S.C. 5309", "citation_type": "usc"},
        ],
    },
    "timeline_and_future_funding": {
        "timeline_to_complete": "24 months from funding receipt",
        "requires_future_federal_funding": False,
        "can_start_with_partial_funding": True,
    },
    "authorization_and_budget": {
        "authorized_in_law": "Yes – 49 U.S.C. 5309",
        "presidential_budget_request": "N/A",
        "prior_funding": "No",
        "non_federal_cost_share_required": True,
        "cost_share_explanation": "City providing $4.7M local match (57%)",
    },
    "risk_and_priority": {
        "derogatory_information_exists": False,
        "derogatory_information_explanation": None,
        "priority_rank_if_multiple": "1",
    },
    "other_offices": {
        "other_members_receiving_request": "Rep. Kay Granger",
    },
    "compliance": {
        "tx11_based_claimed": True,
        "tx11_benefit_claimed": "Project is located in TX-11 and benefits district residents",
        "letters_of_support_count_mentioned": 3,
    },
    "flags": [],
}


def test_upload_single_cpf_record():
    resp = client.post("/api/upload/cpf-json", json=SAMPLE_CPF_RECORD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert len(data["requests"]) == 1
    assert data["errors"] == []

    req = data["requests"][0]
    assert req["title"] == "Downtown Transit Hub Expansion"
    assert req["request_type"] == "cpf"
    assert req["subcommittee"] == "transportation_hud"
    assert req["organization"] == "City of Arlington"
    assert req["amount"] == 3_500_000
    assert req["status"] == "submitted"


def test_upload_batch_cpf_records():
    second = dict(SAMPLE_CPF_RECORD)
    second = {
        **SAMPLE_CPF_RECORD,
        "requesting_organization": {
            **SAMPLE_CPF_RECORD["requesting_organization"],
            "name": "University of Texas at Arlington",
        },
        "project": {
            **SAMPLE_CPF_RECORD["project"],
            "project_name": "STEM Research Lab Renovation",
            "requested_amount": "$1,200,000",
        },
    }
    resp = client.post("/api/upload/cpf-json", json=[SAMPLE_CPF_RECORD, second])
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 2
    assert len(data["requests"]) == 2


def test_upload_handles_invalid_item():
    resp = client.post("/api/upload/cpf-json", json=[SAMPLE_CPF_RECORD, "not a dict"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert len(data["errors"]) == 1
    assert "expected a JSON object" in data["errors"][0]


def test_upload_minimal_cpf_record():
    minimal = {
        "project": {
            "project_name": "Minimal Test Project",
            "requested_amount": 500000,
            "subcommittee": "agriculture",
        },
        "requesting_organization": {"name": "Test Org"},
        "point_of_contact": {"name": "Test Person", "email": "test@test.com"},
    }
    resp = client.post("/api/upload/cpf-json", json=minimal)
    assert resp.status_code == 200
    data = resp.json()
    assert data["created"] == 1
    assert data["requests"][0]["title"] == "Minimal Test Project"
    assert data["requests"][0]["amount"] == 500_000


def test_upload_amount_shorthand():
    record = {
        "project": {
            "project_name": "Shorthand Amount Test",
            "requested_amount": "$1.5M",
            "subcommittee": "defense",
        },
        "requesting_organization": {"name": "Test"},
    }
    resp = client.post("/api/upload/cpf-json", json=record)
    assert resp.status_code == 200
    assert resp.json()["requests"][0]["amount"] == 1_500_000


def test_csv_export():
    resp = client.post("/api/upload/cpf-csv", json=SAMPLE_CPF_RECORD)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    content = resp.text
    lines = content.strip().split("\n")
    assert len(lines) == 2  # header + 1 row
    assert "fiscal_year" in lines[0]
    assert "City of Arlington" in lines[1]
    assert "Downtown Transit Hub Expansion" in lines[1]


def test_csv_export_batch():
    resp = client.post("/api/upload/cpf-csv", json=[SAMPLE_CPF_RECORD, SAMPLE_CPF_RECORD])
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 3  # header + 2 rows


def test_subcommittee_mapping_from_text():
    record = {
        "project": {
            "project_name": "Commerce Test",
            "subcommittee": "Commerce, Justice, Science",
        },
        "requesting_organization": {"name": "Test Org"},
    }
    resp = client.post("/api/upload/cpf-json", json=record)
    assert resp.status_code == 200
    assert resp.json()["requests"][0]["subcommittee"] == "commerce_justice_science"


def test_entity_type_normalization():
    record = {
        "project": {"project_name": "Entity Test", "subcommittee": "agriculture"},
        "requesting_organization": {
            "name": "Local Nonprofit",
            "entity_type_raw": "501(c)(3) nonprofit",
        },
    }
    resp = client.post("/api/upload/cpf-json", json=record)
    assert resp.status_code == 200
    req_id = resp.json()["requests"][0]["id"]
    detail = client.get(f"/api/requests/{req_id}/cpf")
    assert detail.status_code == 200
    assert detail.json()["entity_type"] == "nonprofit_501c3"
