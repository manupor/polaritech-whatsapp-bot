"""
Tests for conversation context surviving serverless cold starts.

`conversation_store` is in-memory, so on Vercel every request starts with an
empty store. `hydrate_flow` restores the flow from the DB snapshot, and
`register_image_analysis` credits photos to the active flow.
"""

import pytest

from src.core.constants import Intent
from src.db.database import get_db, init_db
from src.db import repositories as repo
from src.services.persistence_service import hydrate_flow
from src.services.response_service import register_image_analysis
from src.state.conversation_store import conversation_store


@pytest.fixture(autouse=True)
def _clean_state():
    init_db()
    yield
    conversation_store.clear("+50611110000")
    conversation_store.clear("+50611110001")
    conversation_store.clear("+50611110002")


# ── hydrate_flow ─────────────────────────────────────────────────────────────

def test_hydrate_flow_restores_flow_type_and_fields():
    phone = "+50611110000"
    db = get_db()
    try:
        repo.upsert_contact(db, phone, "Test")
        repo.upsert_snapshot(
            db,
            phone_number=phone,
            current_intent="quote_request",
            flow_type="quote",
            collected_fields={"provincia": "San José", "necesidad": "calor"},
            missing_fields=["fotografias", "medidas", "zona"],
        )
        db.commit()
    finally:
        db.close()

    # Simulate a cold start: nothing in memory
    conversation_store.clear(phone)
    assert conversation_store.get_flow(phone).flow_type == ""

    hydrate_flow(phone)

    flow = conversation_store.get_flow(phone)
    assert flow.flow_type == "quote"
    assert flow.collected["provincia"] == "San José"
    assert flow.collected["necesidad"] == "calor"


def test_hydrate_flow_restores_no_measurements_flag():
    phone = "+50611110001"
    db = get_db()
    try:
        repo.upsert_contact(db, phone, "Test")
        # "medidas" in neither collected nor missing → user has no measurements
        repo.upsert_snapshot(
            db,
            phone_number=phone,
            current_intent="quote_request",
            flow_type="quote",
            collected_fields={"provincia": "Heredia"},
            missing_fields=["fotografias", "zona", "necesidad"],
        )
        db.commit()
    finally:
        db.close()

    conversation_store.clear(phone)
    hydrate_flow(phone)

    assert conversation_store.get_flow(phone).no_measurements is True


def test_hydrate_flow_noop_without_snapshot():
    phone = "+50611110002"
    conversation_store.clear(phone)

    hydrate_flow(phone)

    assert conversation_store.get_flow(phone).flow_type == ""


def test_hydrate_flow_does_not_overwrite_live_state():
    phone = "+50611110000"
    db = get_db()
    try:
        repo.upsert_contact(db, phone, "Test")
        repo.upsert_snapshot(
            db,
            phone_number=phone,
            current_intent="quote_request",
            flow_type="quote",
            collected_fields={"provincia": "San José"},
            missing_fields=["zona"],
        )
        db.commit()
    finally:
        db.close()

    conversation_store.set_flow(phone, "warranty")
    conversation_store.update_flow(phone, {"producto": "Nano Cerámica"})

    hydrate_flow(phone)

    flow = conversation_store.get_flow(phone)
    assert flow.flow_type == "warranty"
    assert flow.collected["producto"] == "Nano Cerámica"
    assert "provincia" not in flow.collected


# ── register_image_analysis ──────────────────────────────────────────────────

def test_register_image_analysis_credits_photos_to_quote_flow():
    phone = "+50611110000"
    conversation_store.clear(phone)
    conversation_store.set_flow(phone, "quote")
    conversation_store.update_flow(phone, {"provincia": "San José"})

    response = register_image_analysis(phone, "Ventanas de vidrio de 2 x 3 metros")

    flow = conversation_store.get_flow(phone)
    assert flow.collected["fotografias"] == "recibidas"
    assert response.intent == Intent.QUOTE_REQUEST
    assert "fotografias" not in flow.quote_missing()


def test_register_image_analysis_extracts_measurements():
    phone = "+50611110000"
    conversation_store.clear(phone)
    conversation_store.set_flow(phone, "quote")

    register_image_analysis(phone, "Se observan ventanas de 2.5 x 3 metros")

    assert "medidas" in conversation_store.get_flow(phone).collected


def test_register_image_analysis_starts_quote_flow_when_none():
    phone = "+50611110001"
    conversation_store.clear(phone)

    response = register_image_analysis(phone, "Ventana de vidrio")

    assert conversation_store.get_flow(phone).flow_type == "quote"
    assert response.intent == Intent.QUOTE_REQUEST


def test_register_image_analysis_lists_missing_fields():
    phone = "+50611110002"
    conversation_store.clear(phone)
    conversation_store.set_flow(phone, "quote")

    response = register_image_analysis(phone, "Ventana de vidrio sin medidas visibles")

    assert "aún necesito" in response.reply_text
    assert "Provincia" in response.reply_text or "provincia" in response.reply_text


def test_register_image_analysis_completes_flow_when_ready():
    phone = "+50611110000"
    conversation_store.clear(phone)
    conversation_store.set_flow(phone, "quote")
    conversation_store.update_flow(phone, {
        "medidas": "2 x 3",
        "provincia": "San José",
        "zona": "Escazú",
        "necesidad": "calor",
    })

    response = register_image_analysis(phone, "Ventanas de vidrio")

    assert "asesor le contactará" in response.reply_text
    assert conversation_store.get_flow(phone).quote_ready() is True


def test_register_image_analysis_keeps_warranty_flow():
    phone = "+50611110001"
    conversation_store.clear(phone)
    conversation_store.set_flow(phone, "warranty")

    response = register_image_analysis(phone, "Película despegada en la esquina")

    assert conversation_store.get_flow(phone).flow_type == "warranty"
    assert response.intent == Intent.WARRANTY_CLAIM
