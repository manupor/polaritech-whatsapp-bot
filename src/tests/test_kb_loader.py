"""Tests proving the real Polaritech KB loads correctly from source files."""

from src.kb.loader import load_faq_json, load_md_articles
from src.kb.models import PENDING, is_pending


# ── JSON loading ─────────────────────────────────────────────────────────────

def test_faq_json_loads():
    kb = load_faq_json()
    assert kb.integrity_rule != ""
    assert len(kb.products) == 6
    assert len(kb.faq) == 50
    assert len(kb.pricing_rules) > 0
    assert len(kb.installation_rules) > 0
    assert len(kb.technical_visits) > 0
    assert len(kb.chatbot_rules) > 0


def test_company_info_loaded():
    kb = load_faq_json()
    assert kb.company.nombre_comercial == "Polaritech Window Film"
    assert "2016" in kb.company.historia
    assert kb.company.sitio_web == "www.polaritech.net"
    assert "Tibás" in kb.company.ubicacion or "Tibas" in kb.company.ubicacion


def test_all_six_products():
    kb = load_faq_json()
    names = [p.nombre for p in kb.products]
    assert any("Nano Cerámica" in n for n in names)
    assert any("Económica" in n or "Economic" in n for n in names)
    assert any("Silver" in n for n in names)
    assert any("Seguridad" in n for n in names)
    assert any("Sand Blasting" in n for n in names)
    assert any("White Out" in n or "Black Out" in n for n in names)


def test_nano_ceramica_specs():
    kb = load_faq_json()
    nc = kb.get_product_by_name("Nano Cerámica")
    assert nc is not None
    assert nc.datos.garantia == "12 años"
    assert "98%" in nc.datos.irr
    assert "99.5%" in nc.datos.uv
    assert not nc.datos.garantia.startswith(PENDING)


def test_economica_specs():
    kb = load_faq_json()
    ec = kb.get_product_by_name("Economic")
    assert ec is not None
    assert ec.datos.garantia == "5 años"
    assert "65%" in ec.datos.irr


def test_policies_loaded():
    kb = load_faq_json()
    assert len(kb.policies.garantia) >= 2
    assert len(kb.policies.limpieza_mantenimiento) >= 2
    assert len(kb.policies.reserva_pagos) >= 1


def test_special_cases_loaded():
    kb = load_faq_json()
    assert len(kb.special_cases) >= 7
    case_names = [c.case for c in kb.special_cases]
    assert any("descuento" in c.lower() for c in case_names)
    assert any("garantía" in c.lower() or "garantia" in c.lower() for c in case_names)


def test_faq_entries_have_content():
    kb = load_faq_json()
    for entry in kb.faq:
        assert entry.question.strip() != ""
        assert entry.answer.strip() != ""


# ── Markdown loading ─────────────────────────────────────────────────────────

def test_md_articles_load():
    articles = load_md_articles()
    assert len(articles) > 0
    topics = [a.topic for a in articles]
    # The MD has sections for company, products, installation, etc.
    assert any("empresa" in t.lower() or "nombre" in t.lower() for t in topics)


# ── Pending information detection ────────────────────────────────────────────

def test_pending_fields_detected():
    """The loader must auto-detect all unconfirmed fields."""
    kb = load_faq_json()
    assert len(kb.pending_information) > 0


def test_company_pending_fields():
    kb = load_faq_json()
    company_pending = [p for p in kb.pending_information if p.startswith("company.")]
    # horario, telefono_whatsapp, correo, redes_sociales are all pending
    assert len(company_pending) >= 4
    assert "company.horario" in company_pending
    assert "company.correo" in company_pending


def test_seguridad_specs_pending():
    """Película de Seguridad has pending espesor and garantía."""
    kb = load_faq_json()
    seg = kb.get_product_by_name("Seguridad")
    assert seg is not None
    assert is_pending(seg.datos.espesor)
    assert is_pending(seg.datos.garantia)
    assert seg.has_pending_specs()


def test_sand_blasting_specs_pending():
    kb = load_faq_json()
    sb = kb.get_product_by_name("Sand Blasting")
    assert sb is not None
    assert is_pending(sb.datos.espesor)
    assert is_pending(sb.datos.garantia)
    assert sb.has_pending_specs()


def test_white_out_black_out_specs_pending():
    kb = load_faq_json()
    wo = kb.get_product_by_name("White Out")
    assert wo is not None
    assert is_pending(wo.datos.especificaciones)
    assert is_pending(wo.datos.garantia)
    assert wo.has_pending_specs()


def test_silver_espejo_guarantee_conflicting():
    """Silver Espejo has a conflicting guarantee reference (6 vs 7 years)."""
    kb = load_faq_json()
    se = kb.get_product_by_name("Silver")
    assert se is not None
    # The guarantee text should mention the conflict, not be a clean number
    assert "6" in se.datos.garantia
    # It should NOT be marked as fully pending, but should contain a caveat
    assert not is_pending(se.datos.garantia)


def test_financing_pending():
    kb = load_faq_json()
    financing_rules = [r for r in kb.pricing_rules if "financiamiento" in r.lower()]
    assert len(financing_rules) >= 1
    assert is_pending(financing_rules[0])


def test_technical_visit_cost_pending():
    kb = load_faq_json()
    cost_rules = [r for r in kb.technical_visits if "costo" in r.lower()]
    assert len(cost_rules) >= 1
    assert is_pending(cost_rules[0])


def test_cancellation_policy_pending():
    kb = load_faq_json()
    cancellation = kb.policies.devoluciones_cancelaciones
    assert len(cancellation) >= 1
    assert is_pending(cancellation[0])


def test_warranty_exclusions_pending():
    kb = load_faq_json()
    garantia_items = kb.policies.garantia
    exclusion_items = [g for g in garantia_items if "exclusion" in g.lower()]
    assert len(exclusion_items) >= 1
    assert is_pending(exclusion_items[0])


def test_is_pending_helper():
    assert is_pending(PENDING)
    assert is_pending("Información pendiente de confirmar.")
    assert is_pending("Algo: Información pendiente de confirmar")
    assert not is_pending("12 años")
    assert not is_pending("")
    assert not is_pending(42)
