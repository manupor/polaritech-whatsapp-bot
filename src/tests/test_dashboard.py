"""
Tests for the internal operations dashboard.
"""

from fastapi.testclient import TestClient

from src.db.database import get_db
from src.db import repositories as repo
from src.main import app

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

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


# ── Dashboard Home ───────────────────────────────────────────────────────────

def test_dashboard_home_200():
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    assert "Panel de Operaciones" in resp.text


def test_dashboard_home_shows_counts():
    _seed_escalation()  # creates with status="open" by default
    _seed_lead()  # creates with status="new" by default
    resp = client.get("/dashboard/")
    assert resp.status_code == 200
    # Should contain at least "1" for both counts
    assert "Escalaciones Abiertas" in resp.text
    assert "Leads Nuevos" in resp.text


# ── Escalations List ─────────────────────────────────────────────────────────

def test_escalations_list_empty():
    resp = client.get("/dashboard/escalations")
    assert resp.status_code == 200
    assert "No hay escalaciones" in resp.text


def test_escalations_list_with_records():
    _seed_escalation()
    resp = client.get("/dashboard/escalations")
    assert resp.status_code == 200
    assert "+50688001234" in resp.text


def test_escalations_list_filter_status():
    _seed_escalation(phone_number="+1")
    resp = client.get("/dashboard/escalations", params={"status": "closed"})
    assert resp.status_code == 200
    assert "No hay escalaciones" in resp.text


def test_escalations_list_filter_priority():
    _seed_escalation(priority="high")
    _seed_escalation(phone_number="+2", priority="normal")
    resp = client.get("/dashboard/escalations", params={"priority": "high"})
    assert resp.status_code == 200
    assert "+50688001234" in resp.text


# ── Escalation Detail ────────────────────────────────────────────────────────

def test_escalation_detail_found():
    eid = _seed_escalation(summary="Film is peeling")
    resp = client.get(f"/dashboard/escalations/{eid}")
    assert resp.status_code == 200
    assert "Film is peeling" in resp.text
    assert "+50688001234" in resp.text


def test_escalation_detail_not_found():
    resp = client.get("/dashboard/escalations/99999")
    assert resp.status_code == 404


def test_escalation_status_update():
    eid = _seed_escalation()
    resp = client.post(
        f"/dashboard/escalations/{eid}/status",
        data={"status": "in_progress"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert f"/dashboard/escalations/{eid}" in resp.headers["location"]

    # Verify status changed
    detail = client.get(f"/dashboard/escalations/{eid}")
    assert "in_progress" in detail.text


def test_escalation_status_update_not_found():
    resp = client.post(
        "/dashboard/escalations/99999/status",
        data={"status": "closed"},
    )
    assert resp.status_code == 404


# ── Leads List ───────────────────────────────────────────────────────────────

def test_leads_list_empty():
    resp = client.get("/dashboard/leads")
    assert resp.status_code == 200
    assert "No hay leads" in resp.text


def test_leads_list_with_records():
    _seed_lead()
    resp = client.get("/dashboard/leads")
    assert resp.status_code == 200
    assert "+50688001234" in resp.text


def test_leads_list_filter_status():
    _seed_lead()
    resp = client.get("/dashboard/leads", params={"status": "contacted"})
    assert resp.status_code == 200
    assert "No hay leads" in resp.text


def test_leads_list_filter_type():
    _seed_lead(lead_type="quote")
    _seed_lead(phone_number="+2", lead_type="warranty")
    resp = client.get("/dashboard/leads", params={"lead_type": "quote"})
    assert resp.status_code == 200
    assert "+50688001234" in resp.text


# ── Lead Detail ──────────────────────────────────────────────────────────────

def test_lead_detail_found():
    lid = _seed_lead(province="San José", main_need="calor")
    resp = client.get(f"/dashboard/leads/{lid}")
    assert resp.status_code == 200
    assert "San José" in resp.text
    assert "calor" in resp.text


def test_lead_detail_not_found():
    resp = client.get("/dashboard/leads/99999")
    assert resp.status_code == 404


def test_lead_status_update():
    lid = _seed_lead()
    resp = client.post(
        f"/dashboard/leads/{lid}/status",
        data={"status": "contacted"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert f"/dashboard/leads/{lid}" in resp.headers["location"]

    detail = client.get(f"/dashboard/leads/{lid}")
    assert "contacted" in detail.text


def test_lead_status_update_not_found():
    resp = client.post(
        "/dashboard/leads/99999/status",
        data={"status": "closed"},
    )
    assert resp.status_code == 404


# ── Conversation Lookup ──────────────────────────────────────────────────────

def test_conversation_lookup_page():
    resp = client.get("/dashboard/conversations")
    assert resp.status_code == 200
    assert "Buscar conversación" in resp.text


def test_conversation_lookup_found():
    db = get_db()
    try:
        repo.upsert_contact(db, "+50688001234", "María Test")
        repo.upsert_snapshot(
            db,
            phone_number="+50688001234",
            current_intent="quote_request",
            flow_type="quote",
            collected_fields={"provincia": "Heredia"},
            missing_fields=["medidas"],
            last_bot_response="Gracias.",
        )
        db.commit()
    finally:
        db.close()

    resp = client.get("/dashboard/conversations", params={"phone": "+50688001234"})
    assert resp.status_code == 200
    assert "María Test" in resp.text
    assert "quote_request" in resp.text
    assert "provincia: Heredia" in resp.text
    assert "medidas" in resp.text


def test_conversation_lookup_not_found():
    resp = client.get("/dashboard/conversations", params={"phone": "+0000000000"})
    assert resp.status_code == 200
    assert "No se encontró" in resp.text
