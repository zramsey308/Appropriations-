"""Tests for CPF validation and selection workflow."""
from fastapi.testclient import TestClient
from app.main import app
from app.models import CPFDetails

client = TestClient(app)


def _create_cpf_request():
    resp = client.post("/api/requests", json={
        "request_type": "cpf",
        "subcommittee": "transportation_hud",
        "title": "Transit Hub Renovation",
        "requested_amount": 2500000,
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _add_cpf_details(request_id, **overrides):
    data = {
        "cpf_account_id": 1,
        "tx11_nexus": True,
        "tx11_nexus_explanation": "Project located in TX-11",
        "entity_type": "local_government",
        "entity_name": "City of Springfield",
        "entity_address": "123 Main St",
        "project_name": "Transit Hub Renovation",
        "project_address": "500 Transit Way",
        "project_description": "Renovate the hub",
        "requested_amount": 2500000,
        "total_project_cost": 5000000,
        "cost_share_required": False,
        "public_benefit_justification": "Serves 50k commuters",
    }
    data.update(overrides)
    resp = client.post(f"/api/requests/{request_id}/cpf", json=data)
    assert resp.status_code == 201
    return resp.json()


def _set_support_letters(request_id, db_session, count=3):
    """Directly set support_letters_received for testing."""
    cpf_record = db_session.query(CPFDetails).filter(CPFDetails.request_id == request_id).first()
    cpf_record.support_letters_received = count
    db_session.commit()


# ── CPF Details CRUD ──────────────────────────────────────

def test_create_cpf_details():
    rid = _create_cpf_request()
    cpf = _add_cpf_details(rid)
    assert cpf["request_id"] == rid
    assert cpf["entity_name"] == "City of Springfield"
    assert cpf["tx11_nexus"] is True


def test_get_cpf_details():
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    resp = client.get(f"/api/requests/{rid}/cpf")
    assert resp.status_code == 200
    assert resp.json()["project_name"] == "Transit Hub Renovation"


def test_cpf_details_not_found():
    resp = client.get("/api/requests/99999/cpf")
    assert resp.status_code == 404


def test_update_cpf_details():
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    resp = client.post(f"/api/requests/{rid}/cpf", json={
        "entity_name": "Updated City",
        "tx11_nexus": True,
    })
    assert resp.status_code == 201
    assert resp.json()["entity_name"] == "Updated City"


def test_cpf_on_non_cpf_request():
    resp = client.post("/api/requests", json={
        "request_type": "programmatic",
        "subcommittee": "defense",
        "title": "Defense Program",
    })
    rid = resp.json()["id"]
    resp = client.post(f"/api/requests/{rid}/cpf", json={
        "tx11_nexus": True,
        "entity_type": "local_government",
    })
    assert resp.status_code == 400
    assert "cpf" in resp.json()["detail"].lower()


# ── CPF Validation ──────────────────────────────────────

def test_validate_cpf_passing(db_session):
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    _set_support_letters(rid, db_session, 3)

    resp = client.post(f"/api/requests/{rid}/cpf/validate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True
    assert len(body["missing_requirements"]) == 0


def test_validate_cpf_failing_no_support_letters():
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    resp = client.post(f"/api/requests/{rid}/cpf/validate")
    body = resp.json()
    assert body["passed"] is False
    assert any("support letters" in req.lower() for req in body["missing_requirements"])


def test_validate_cpf_failing_no_tx11():
    rid = _create_cpf_request()
    _add_cpf_details(rid, tx11_nexus=False)
    resp = client.post(f"/api/requests/{rid}/cpf/validate")
    body = resp.json()
    assert body["passed"] is False
    assert any("tx-11" in req.lower() for req in body["missing_requirements"])


def test_validate_cpf_cost_share_required_without_explanation():
    rid = _create_cpf_request()
    _add_cpf_details(rid, cost_share_required=True, cost_share_explanation="")
    resp = client.post(f"/api/requests/{rid}/cpf/validate")
    body = resp.json()
    assert body["passed"] is False
    assert any("cost share" in req.lower() for req in body["missing_requirements"])


# ── CPF Selection ──────────────────────────────────────

def test_select_cpf_fails_without_validation():
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    resp = client.post(f"/api/requests/{rid}/cpf/select")
    assert resp.status_code == 400
    assert "validation failed" in resp.json()["detail"].lower()


def test_select_cpf_success(db_session):
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    _set_support_letters(rid, db_session, 3)

    resp = client.post(f"/api/requests/{rid}/cpf/select")
    assert resp.status_code == 200
    body = resp.json()
    assert body["selected"] is True
    assert body["selected_slot"] == 1


def test_select_cpf_specific_slot(db_session):
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    _set_support_letters(rid, db_session, 3)

    resp = client.post(f"/api/requests/{rid}/cpf/select?slot=5")
    assert resp.status_code == 200
    assert resp.json()["selected_slot"] == 5


def test_select_cpf_duplicate_rejected(db_session):
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    _set_support_letters(rid, db_session, 3)

    resp = client.post(f"/api/requests/{rid}/cpf/select")
    assert resp.status_code == 200

    # Try selecting again
    resp = client.post(f"/api/requests/{rid}/cpf/select")
    assert resp.status_code == 400
    assert "already selected" in resp.json()["detail"].lower()


def test_select_cpf_invalid_slot(db_session):
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    _set_support_letters(rid, db_session, 3)

    resp = client.post(f"/api/requests/{rid}/cpf/select?slot=16")
    assert resp.status_code == 400
    assert "slot" in resp.json()["detail"].lower()


# ── Attachments ──────────────────────────────────────

def test_list_attachments_empty():
    rid = _create_cpf_request()
    resp = client.get(f"/api/requests/{rid}/attachments")
    assert resp.status_code == 200
    assert resp.json() == []


# ── Request cascading delete ──────────────────────────

def test_delete_request_cascades_cpf():
    rid = _create_cpf_request()
    _add_cpf_details(rid)
    assert client.get(f"/api/requests/{rid}/cpf").status_code == 200
    client.delete(f"/api/requests/{rid}")
    assert client.get(f"/api/requests/{rid}/cpf").status_code == 404
