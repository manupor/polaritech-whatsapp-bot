"""
Tests for the internal Ops API endpoints.
"""

from fastapi.testclient import TestClient

from src.db.database import get_db
from src.db import repositories as repo
from src.main import app


client = TestClient(app)


# ── /ops/health ──────────────────────────────────────────────────────────────

def test_ops_health():
    resp = client.get("/ops/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Escalation endpoints ────────────────────────────────────────────────────

def _seed_escalation(**kwargs):
    db = get_db()
    try:
        defaults = dict(
            phone_number="+50688001234",
            intent="warranty_claim",
            summary="Test escalation",
            priority="high",
        )
        defaults.update(kwargs)
        rec = repo.create_escalation(db, **defaults)
        db.commit()
        return rec.id
    finally:
        db.close()


def test_list_escalations_empty():
    resp = client.get("/ops/escalations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_escalations_with_data():
    _seed_escalation()
    _seed_escalation(phone_number="+50688005678", priority="normal")
    resp = client.get("/ops/escalations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_escalations_filter_priority():
    _seed_escalation(priority="high")
    _seed_escalation(phone_number="+50688005678", priority="normal")
    resp = client.get("/ops/escalations", params={"priority": "high"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["priority"] == "high"


def test_list_escalations_filter_status():
    eid = _seed_escalation()
    # Update one to in_progress
    db = get_db()
    try:
        repo.update_escalation_status(db, eid, "in_progress")
        db.commit()
    finally:
        db.close()
    _seed_escalation(phone_number="+2")

    resp = client.get("/ops/escalations", params={"status": "open"})
    data = resp.json()
    assert data["total"] == 1


def test_get_escalation_found():
    eid = _seed_escalation()
    resp = client.get(f"/ops/escalations/{eid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == eid


def test_get_escalation_not_found():
    resp = client.get("/ops/escalations/99999")
    assert resp.status_code == 404


def test_patch_escalation_status():
    eid = _seed_escalation()
    resp = client.patch(
        f"/ops/escalations/{eid}/status",
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


def test_patch_escalation_invalid_status():
    eid = _seed_escalation()
    resp = client.patch(
        f"/ops/escalations/{eid}/status",
        json={"status": "invalid_status"},
    )
    assert resp.status_code == 422


def test_patch_escalation_not_found():
    resp = client.patch(
        "/ops/escalations/99999/status",
        json={"status": "closed"},
    )
    assert resp.status_code == 404


# ── Lead endpoints ──────────────────────────────────────────────────────────

def _seed_lead(**kwargs):
    db = get_db()
    try:
        defaults = dict(
            phone_number="+50688001234",
            lead_type="quote",
            province="Heredia",
        )
        defaults.update(kwargs)
        rec = repo.upsert_lead(db, **defaults)
        db.commit()
        return rec.id
    finally:
        db.close()


def test_list_leads_empty():
    resp = client.get("/ops/leads")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_list_leads_with_data():
    _seed_lead()
    _seed_lead(phone_number="+50688005678", lead_type="warranty")
    resp = client.get("/ops/leads")
    data = resp.json()
    assert data["total"] == 2


def test_list_leads_filter_type():
    _seed_lead(lead_type="quote")
    _seed_lead(phone_number="+2", lead_type="warranty")
    resp = client.get("/ops/leads", params={"lead_type": "quote"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["lead_type"] == "quote"


def test_list_leads_filter_status():
    lid = _seed_lead()
    db = get_db()
    try:
        repo.update_lead_status(db, lid, "contacted")
        db.commit()
    finally:
        db.close()
    _seed_lead(phone_number="+2")

    resp = client.get("/ops/leads", params={"status": "new"})
    data = resp.json()
    assert data["total"] == 1


def test_get_lead_found():
    lid = _seed_lead()
    resp = client.get(f"/ops/leads/{lid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == lid
    assert resp.json()["province"] == "Heredia"


def test_get_lead_not_found():
    resp = client.get("/ops/leads/99999")
    assert resp.status_code == 404


def test_patch_lead_status():
    lid = _seed_lead()
    resp = client.patch(
        f"/ops/leads/{lid}/status",
        json={"status": "quoted"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "quoted"


def test_patch_lead_invalid_status():
    lid = _seed_lead()
    resp = client.patch(
        f"/ops/leads/{lid}/status",
        json={"status": "nonexistent"},
    )
    assert resp.status_code == 422


def test_patch_lead_not_found():
    resp = client.patch(
        "/ops/leads/99999/status",
        json={"status": "closed"},
    )
    assert resp.status_code == 404


# ── Conversation endpoint ───────────────────────────────────────────────────

def test_get_conversation_found():
    db = get_db()
    try:
        repo.upsert_contact(db, "+50688001234", "María")
        repo.upsert_snapshot(
            db,
            phone_number="+50688001234",
            current_intent="quote_request",
            flow_type="quote",
            collected_fields={"provincia": "Heredia"},
            missing_fields=["medidas"],
            needs_human=False,
            last_bot_response="Gracias por la información.",
        )
        db.commit()
    finally:
        db.close()

    resp = client.get("/ops/conversations/+50688001234")
    assert resp.status_code == 200
    data = resp.json()
    assert data["phone_number"] == "+50688001234"
    assert data["profile_name"] == "María"
    assert data["current_intent"] == "quote_request"
    assert data["collected_fields"]["provincia"] == "Heredia"
    assert "medidas" in data["missing_fields"]


def test_get_conversation_not_found():
    resp = client.get("/ops/conversations/+0000000000")
    assert resp.status_code == 404


# ── Pagination ──────────────────────────────────────────────────────────────

def test_escalations_pagination():
    for i in range(5):
        _seed_escalation(phone_number=f"+{i}")
    resp = client.get("/ops/escalations", params={"limit": 2, "offset": 0})
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_leads_pagination():
    for i in range(5):
        _seed_lead(phone_number=f"+{i}")
    resp = client.get("/ops/leads", params={"limit": 3, "offset": 2})
    data = resp.json()
    assert len(data["items"]) == 3
    assert data["offset"] == 2
