"""
Tests for repository CRUD, persistence service hooks, lead creation on
quote handoff, escalation records on warranty/visit, and snapshot sync.
"""

import json

from src.core.constants import Intent
from src.db.database import get_db
from src.db import repositories as repo
from src.db.models import Contact, MessageLog, ConversationSnapshot, EscalationRecord, LeadRecord
from src.schemas.chatbot import BotResponse, EscalationPayload, IncomingMessage
from src.services.persistence_service import persist_inbound, persist_outbound
from src.state.conversation_store import conversation_store


# ── Repository: Contact ─────────────────────────────────────────────────────

def test_upsert_contact_create():
    db = get_db()
    try:
        c = repo.upsert_contact(db, "+50688001234", "Ana")
        db.commit()
        assert c.phone_number == "+50688001234"
        assert c.profile_name == "Ana"
        assert c.first_seen_at is not None
    finally:
        db.close()


def test_upsert_contact_update():
    db = get_db()
    try:
        repo.upsert_contact(db, "+50688001234", "Ana")
        db.commit()
        c = repo.upsert_contact(db, "+50688001234", "Ana García")
        db.commit()
        assert c.profile_name == "Ana García"
        # Should still be only one contact
        count = db.query(Contact).filter(Contact.phone_number == "+50688001234").count()
        assert count == 1
    finally:
        db.close()


def test_upsert_contact_unknown_name_no_overwrite():
    db = get_db()
    try:
        repo.upsert_contact(db, "+50688001234", "Ana")
        db.commit()
        c = repo.upsert_contact(db, "+50688001234", "Unknown")
        db.commit()
        # Should keep "Ana", not overwrite with "Unknown"
        assert c.profile_name == "Ana"
    finally:
        db.close()


# ── Repository: MessageLog ──────────────────────────────────────────────────

def test_log_message():
    db = get_db()
    try:
        entry = repo.log_message(
            db,
            direction="inbound",
            phone_number="+50688001234",
            text="Hola",
            wa_message_id="wamid.001",
        )
        db.commit()
        assert entry.id is not None
        assert entry.direction == "inbound"
        assert entry.text == "Hola"
    finally:
        db.close()


def test_log_message_truncates_long_text():
    db = get_db()
    try:
        long_text = "a" * 5000
        entry = repo.log_message(
            db,
            direction="inbound",
            phone_number="+50688001234",
            text=long_text,
        )
        db.commit()
        assert len(entry.text) == 4000
    finally:
        db.close()


# ── Repository: ConversationSnapshot ─────────────────────────────────────────

def test_upsert_snapshot_create():
    db = get_db()
    try:
        snap = repo.upsert_snapshot(
            db,
            phone_number="+50688001234",
            current_intent="greeting",
            flow_type="",
            needs_human=False,
        )
        db.commit()
        assert snap.phone_number == "+50688001234"
        assert snap.current_intent == "greeting"
        assert snap.needs_human == 0
    finally:
        db.close()


def test_upsert_snapshot_update():
    db = get_db()
    try:
        repo.upsert_snapshot(
            db,
            phone_number="+50688001234",
            current_intent="greeting",
        )
        db.commit()
        snap = repo.upsert_snapshot(
            db,
            phone_number="+50688001234",
            current_intent="quote_request",
            flow_type="quote",
            collected_fields={"provincia": "Heredia"},
            missing_fields=["medidas", "necesidad"],
            needs_human=False,
        )
        db.commit()
        assert snap.current_intent == "quote_request"
        assert snap.flow_type == "quote"
        parsed = json.loads(snap.collected_fields_json)
        assert parsed["provincia"] == "Heredia"
        # Only one snapshot per phone
        count = db.query(ConversationSnapshot).filter(
            ConversationSnapshot.phone_number == "+50688001234"
        ).count()
        assert count == 1
    finally:
        db.close()


# ── Repository: EscalationRecord ─────────────────────────────────────────────

def test_create_escalation():
    db = get_db()
    try:
        rec = repo.create_escalation(
            db,
            phone_number="+50688001234",
            intent="warranty_claim",
            summary="Película despegándose",
            priority="high",
            collected_fields={"descripcion": "se despegó"},
            missing_fields=["fotografias"],
        )
        db.commit()
        assert rec.id is not None
        assert rec.status == "open"
        assert rec.priority == "high"
    finally:
        db.close()


def test_list_escalations_filter_status():
    db = get_db()
    try:
        repo.create_escalation(db, phone_number="+1", intent="warranty_claim", priority="high")
        repo.create_escalation(db, phone_number="+2", intent="technical_visit", priority="normal")
        db.commit()

        all_recs = repo.list_escalations(db)
        assert len(all_recs) == 2

        open_recs = repo.list_escalations(db, status="open")
        assert len(open_recs) == 2

        high_recs = repo.list_escalations(db, priority="high")
        assert len(high_recs) == 1
    finally:
        db.close()


def test_update_escalation_status():
    db = get_db()
    try:
        rec = repo.create_escalation(
            db, phone_number="+50688001234", intent="warranty_claim", priority="high",
        )
        db.commit()
        updated = repo.update_escalation_status(db, rec.id, "in_progress")
        db.commit()
        assert updated.status == "in_progress"
    finally:
        db.close()


# ── Repository: LeadRecord ──────────────────────────────────────────────────

def test_upsert_lead_create():
    db = get_db()
    try:
        lead = repo.upsert_lead(
            db,
            phone_number="+50688001234",
            lead_type="quote",
            province="Heredia",
            zone="Santo Domingo",
            main_need="calor",
        )
        db.commit()
        assert lead.id is not None
        assert lead.status == "new"
        assert lead.province == "Heredia"
    finally:
        db.close()


def test_upsert_lead_update_existing():
    db = get_db()
    try:
        lead1 = repo.upsert_lead(
            db,
            phone_number="+50688001234",
            lead_type="quote",
            province="Heredia",
        )
        db.commit()
        lead2 = repo.upsert_lead(
            db,
            phone_number="+50688001234",
            lead_type="quote",
            zone="Santo Domingo",
            measurements="5 m²",
        )
        db.commit()
        assert lead1.id == lead2.id
        assert lead2.province == "Heredia"
        assert lead2.zone == "Santo Domingo"
        assert lead2.measurements == "5 m²"
    finally:
        db.close()


def test_list_leads_filter():
    db = get_db()
    try:
        repo.upsert_lead(db, phone_number="+1", lead_type="quote")
        repo.upsert_lead(db, phone_number="+2", lead_type="warranty")
        db.commit()

        quotes = repo.list_leads(db, lead_type="quote")
        assert len(quotes) == 1

        all_leads = repo.list_leads(db)
        assert len(all_leads) == 2
    finally:
        db.close()


def test_update_lead_status():
    db = get_db()
    try:
        lead = repo.upsert_lead(
            db, phone_number="+50688001234", lead_type="quote",
        )
        db.commit()
        updated = repo.update_lead_status(db, lead.id, "contacted")
        db.commit()
        assert updated.status == "contacted"
    finally:
        db.close()


# ── Persistence service: inbound ─────────────────────────────────────────────

def test_persist_inbound_creates_contact_and_log():
    msg = IncomingMessage(
        phone_number="+50688009999",
        sender_name="Carlos",
        message_id="wamid.in001",
        text="Hola",
        timestamp="1700000000",
    )
    persist_inbound(msg, wa_message_id="wamid.in001")

    db = get_db()
    try:
        contact = db.query(Contact).filter(Contact.phone_number == "+50688009999").first()
        assert contact is not None
        assert contact.profile_name == "Carlos"

        logs = db.query(MessageLog).filter(MessageLog.phone_number == "+50688009999").all()
        assert len(logs) == 1
        assert logs[0].direction == "inbound"
        assert logs[0].text == "Hola"
    finally:
        db.close()


# ── Persistence service: outbound + snapshot sync ────────────────────────────

def test_persist_outbound_logs_and_syncs_snapshot():
    response = BotResponse(
        phone_number="+50688009999",
        reply_text="¡Bienvenido a Polaritech!",
        intent=Intent.GREETING,
        escalated=False,
    )
    persist_outbound(response)

    db = get_db()
    try:
        logs = db.query(MessageLog).filter(
            MessageLog.phone_number == "+50688009999",
            MessageLog.direction == "outbound",
        ).all()
        assert len(logs) == 1
        assert "Polaritech" in logs[0].text

        snap = db.query(ConversationSnapshot).filter(
            ConversationSnapshot.phone_number == "+50688009999",
        ).first()
        assert snap is not None
        assert snap.current_intent == "greeting"
    finally:
        db.close()


# ── Lead creation on quote handoff ───────────────────────────────────────────

def test_persist_outbound_creates_lead_on_quote_handoff():
    esc = EscalationPayload(
        intent=Intent.QUOTE_REQUEST,
        summary="Cotización lista para seguimiento",
        collected_fields={
            "provincia": "Heredia",
            "zona": "Santo Domingo",
            "medidas": "5 m²",
            "necesidad": "calor",
            "fotografias": "sí",
        },
        missing_fields=[],
        priority="normal",
    )
    response = BotResponse(
        phone_number="+50688009999",
        reply_text="Handoff text",
        intent=Intent.QUOTE_REQUEST,
        escalated=True,
        escalation=esc,
    )
    persist_outbound(response)

    db = get_db()
    try:
        leads = db.query(LeadRecord).filter(
            LeadRecord.phone_number == "+50688009999",
        ).all()
        assert len(leads) == 1
        lead = leads[0]
        assert lead.lead_type == "quote"
        assert lead.province == "Heredia"
        assert lead.zone == "Santo Domingo"
        assert lead.measurements == "5 m²"
        assert lead.main_need == "calor"
        assert lead.has_photos == 1
    finally:
        db.close()


# ── Escalation record on warranty claim ──────────────────────────────────────

def test_persist_outbound_creates_escalation_on_warranty():
    esc = EscalationPayload(
        intent=Intent.WARRANTY_CLAIM,
        summary="Reclamo de garantía — requiere atención",
        collected_fields={"descripcion": "se despegó"},
        missing_fields=["fotografias", "fecha_instalacion", "producto"],
        priority="high",
    )
    response = BotResponse(
        phone_number="+50688009999",
        reply_text="Warranty reply",
        intent=Intent.WARRANTY_CLAIM,
        escalated=True,
        escalation=esc,
    )
    persist_outbound(response)

    db = get_db()
    try:
        records = db.query(EscalationRecord).filter(
            EscalationRecord.phone_number == "+50688009999",
        ).all()
        assert len(records) == 1
        rec = records[0]
        assert rec.intent == "warranty_claim"
        assert rec.priority == "high"
        assert rec.status == "open"
        collected = json.loads(rec.collected_fields_json)
        assert collected["descripcion"] == "se despegó"
    finally:
        db.close()


# ── Escalation record on technical visit ─────────────────────────────────────

def test_persist_outbound_creates_escalation_on_visit():
    esc = EscalationPayload(
        intent=Intent.TECHNICAL_VISIT,
        summary="Solicitud de visita técnica",
        collected_fields={},
        missing_fields=["provincia", "zona", "fotografias", "objetivo"],
        priority="normal",
    )
    response = BotResponse(
        phone_number="+50688009999",
        reply_text="Visit reply",
        intent=Intent.TECHNICAL_VISIT,
        escalated=True,
        escalation=esc,
    )
    persist_outbound(response)

    db = get_db()
    try:
        records = db.query(EscalationRecord).filter(
            EscalationRecord.phone_number == "+50688009999",
        ).all()
        assert len(records) == 1
        assert records[0].intent == "technical_visit"
        assert records[0].priority == "normal"
    finally:
        db.close()


# ── Snapshot syncs with flow state ───────────────────────────────────────────

def test_snapshot_reflects_flow_state():
    """When there's an active quote flow, snapshot should capture collected/missing."""
    phone = "+50688008888"
    conversation_store.set_flow(phone, "quote")
    conversation_store.update_flow(phone, {"provincia": "San José", "necesidad": "calor"})

    response = BotResponse(
        phone_number=phone,
        reply_text="Quote progress reply",
        intent=Intent.QUOTE_REQUEST,
        escalated=False,
    )
    persist_outbound(response)

    db = get_db()
    try:
        snap = db.query(ConversationSnapshot).filter(
            ConversationSnapshot.phone_number == phone,
        ).first()
        assert snap is not None
        assert snap.flow_type == "quote"
        collected = json.loads(snap.collected_fields_json)
        assert collected["provincia"] == "San José"
        missing = json.loads(snap.missing_fields_json)
        assert "fotografias" in missing
        assert "medidas" in missing
    finally:
        db.close()
