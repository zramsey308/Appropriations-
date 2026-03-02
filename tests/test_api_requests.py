"""API-level tests for request CRUD and dashboard endpoints."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Request CRUD ──────────────────────────────────────────────

def _create_cpf_request(**overrides):
    data = {
        "request_type": "cpf",
        "subcommittee": "transportation_hud",
        "title": "Downtown Transit Hub",
        "description": "Renovate the central transit hub",
        "requester_name": "Jane Smith",
        "requester_email": "jane@example.org",
        "requester_organization": "City of Springfield",
        "requested_amount": 2500000,
    }
    data.update(overrides)
    return client.post("/api/requests", json=data)


def test_create_request():
    resp = _create_cpf_request()
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Downtown Transit Hub"
    assert body["request_type"] == "cpf"
    assert body["status"] == "submitted"
    assert body["id"] >= 1


def test_create_programmatic_request():
    resp = client.post("/api/requests", json={
        "request_type": "programmatic",
        "subcommittee": "labor_hhs_education",
        "title": "Increase CHC Funding",
        "program_name": "Health Center Program",
        "requested_amount": 500000000,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["request_type"] == "programmatic"
    assert body["program_name"] == "Health Center Program"


def test_create_language_request():
    resp = client.post("/api/requests", json={
        "request_type": "language",
        "subcommittee": "commerce_justice_science",
        "title": "Rural Broadband Report Language",
        "proposed_language": "The Committee directs NTIA to submit quarterly reports...",
    })
    assert resp.status_code == 201
    assert resp.json()["request_type"] == "language"


def test_get_request():
    create_resp = _create_cpf_request()
    rid = create_resp.json()["id"]
    resp = client.get(f"/api/requests/{rid}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Downtown Transit Hub"


def test_get_request_not_found():
    resp = client.get("/api/requests/99999")
    assert resp.status_code == 404


def test_list_requests():
    _create_cpf_request(title="Request A")
    _create_cpf_request(title="Request B")
    resp = client.get("/api/requests")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_list_requests_filter_by_type():
    _create_cpf_request()
    client.post("/api/requests", json={
        "request_type": "language",
        "subcommittee": "defense",
        "title": "Language Request",
    })
    resp = client.get("/api/requests?type=cpf")
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["request_type"] == "cpf"


def test_list_requests_filter_by_subcommittee():
    _create_cpf_request(subcommittee="transportation_hud")
    _create_cpf_request(subcommittee="defense")
    resp = client.get("/api/requests?subcommittee=defense")
    assert resp.json()["total"] == 1


def test_update_request():
    create_resp = _create_cpf_request()
    rid = create_resp.json()["id"]
    resp = client.patch(f"/api/requests/{rid}", json={
        "title": "Updated Transit Hub",
        "status": "under_review",
    })
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Transit Hub"
    assert resp.json()["status"] == "under_review"


def test_update_request_not_found():
    resp = client.patch("/api/requests/99999", json={"title": "x"})
    assert resp.status_code == 404


def test_delete_request():
    create_resp = _create_cpf_request()
    rid = create_resp.json()["id"]
    resp = client.delete(f"/api/requests/{rid}")
    assert resp.status_code == 204
    assert client.get(f"/api/requests/{rid}").status_code == 404


def test_delete_request_not_found():
    resp = client.delete("/api/requests/99999")
    assert resp.status_code == 404


# ── Text Search ──────────────────────────────────────────────

def test_search_by_title():
    _create_cpf_request(title="Midland Water Treatment")
    _create_cpf_request(title="Odessa Bridge Repair")
    resp = client.get("/api/requests?q=midland")
    assert resp.json()["total"] == 1
    assert "Midland" in resp.json()["items"][0]["title"]


def test_search_by_requester_name():
    _create_cpf_request(requester_name="Jane Smith")
    _create_cpf_request(requester_name="John Doe")
    resp = client.get("/api/requests?q=doe")
    assert resp.json()["total"] == 1


def test_search_by_organization():
    _create_cpf_request(requester_organization="City of Midland")
    _create_cpf_request(requester_organization="Permian Basin Foundation")
    resp = client.get("/api/requests?q=permian")
    assert resp.json()["total"] == 1


def test_search_no_results():
    _create_cpf_request()
    resp = client.get("/api/requests?q=nonexistent")
    assert resp.json()["total"] == 0


# ── CSV Export ──────────────────────────────────────────────

def test_export_csv():
    _create_cpf_request()
    _create_cpf_request(title="Second Request")
    resp = client.get("/api/requests/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    lines = resp.text.strip().split("\n")
    assert len(lines) == 3  # header + 2 data rows
    assert "ID" in lines[0]
    assert "Downtown Transit Hub" in resp.text or "Second Request" in resp.text


def test_export_csv_with_filters():
    _create_cpf_request(subcommittee="transportation_hud")
    client.post("/api/requests", json={
        "request_type": "language",
        "subcommittee": "defense",
        "title": "Defense Language",
    })
    resp = client.get("/api/requests/export.csv?type=cpf")
    lines = resp.text.strip().split("\n")
    assert len(lines) == 2  # header + 1 data row


def test_export_csv_empty():
    resp = client.get("/api/requests/export.csv")
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 1  # header only


# ── Dashboard ──────────────────────────────────────────────

def test_dashboard_summary_empty():
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_requests"] == 0
    assert body["cpf_selected"] == 0
    assert body["cpf_selected_slots_remaining"] == 15


def test_dashboard_summary_with_data():
    _create_cpf_request()
    _create_cpf_request(title="Another CPF")
    client.post("/api/requests", json={
        "request_type": "programmatic",
        "subcommittee": "defense",
        "title": "Defense Program",
        "requested_amount": 1000000,
    })
    resp = client.get("/api/dashboard/summary")
    body = resp.json()
    assert body["total_requests"] == 3
    assert body["by_type"]["cpf"] == 2
    assert body["by_type"]["programmatic"] == 1
    assert body["total_requested_amount"] == 2500000 + 2500000 + 1000000


# ── Eligible Accounts ──────────────────────────────────────

def test_list_eligible_accounts():
    resp = client.get("/api/eligible-accounts")
    assert resp.status_code == 200
    accounts = resp.json()
    assert len(accounts) >= 1


def test_list_eligible_accounts_filter_subcommittee():
    resp = client.get("/api/eligible-accounts?subcommittee=agriculture")
    assert resp.status_code == 200
    for a in resp.json():
        assert a["subcommittee"] == "agriculture"


def test_get_eligible_account():
    resp = client.get("/api/eligible-accounts/1")
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


def test_get_eligible_account_not_found():
    resp = client.get("/api/eligible-accounts/99999")
    assert resp.status_code == 404
