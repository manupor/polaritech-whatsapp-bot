from src.core.constants import Intent
from src.services.intent_service import classify_intent


def test_greeting():
    assert classify_intent("Hola, buenas tardes") == Intent.GREETING
    assert classify_intent("hey there") == Intent.GREETING


def test_quote_request():
    assert classify_intent("¿Cuánto cuesta la película?") == Intent.QUOTE_REQUEST
    assert classify_intent("Necesito una cotización") == Intent.QUOTE_REQUEST
    assert classify_intent("How much does it cost?") == Intent.QUOTE_REQUEST


def test_appointment():
    assert classify_intent("Quiero agendar una cita") == Intent.APPOINTMENT
    assert classify_intent("Can I schedule an appointment?") == Intent.APPOINTMENT


def test_product_info():
    assert classify_intent("Cuéntame sobre la Nano Cerámica") == Intent.PRODUCT_INFO
    assert classify_intent("¿Tienen película de seguridad?") == Intent.PRODUCT_INFO
    assert classify_intent("Quiero info sobre sand blasting") == Intent.PRODUCT_INFO


def test_warranty_claim():
    assert classify_intent("La película se despegó") == Intent.WARRANTY_CLAIM
    assert classify_intent("Tengo un reclamo, la lámina se está despegando") == Intent.WARRANTY_CLAIM


def test_technical_visit():
    assert classify_intent("Necesito una visita técnica") == Intent.TECHNICAL_VISIT
    assert classify_intent("Quiero programar una inspección") == Intent.TECHNICAL_VISIT


def test_competitor():
    assert classify_intent("Me ofrecieron 3M más barato") == Intent.COMPETITOR
    assert classify_intent("¿Trabajan con LLumar?") == Intent.COMPETITOR


def test_discount():
    assert classify_intent("Quiero descuento") == Intent.DISCOUNT
    assert classify_intent("¿Tienen alguna promoción?") == Intent.DISCOUNT


def test_pending_query():
    assert classify_intent("¿Tienen financiamiento?") == Intent.PENDING_QUERY
    assert classify_intent("¿Cuál es la política de cancelación?") == Intent.PENDING_QUERY


def test_escalation():
    assert classify_intent("Quiero hablar con alguien") == Intent.ESCALATE
    assert classify_intent("Necesito un asesor") == Intent.ESCALATE


def test_unknown():
    assert classify_intent("asdfghjkl") == Intent.UNKNOWN


def test_escalation_takes_priority():
    assert classify_intent("Quiero un asesor para una cotización") == Intent.ESCALATE
