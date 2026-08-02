"""
Tests for canonical FAQ answers and pending confirmation fields.
"""

import pytest
from src.services.faq_service import find_answer


def test_canonical_calor_question():
    """Test canonical answer for heat-related question."""
    answer = find_answer("¿Cuál recomiendan si hace mucho calor?")
    assert answer is not None
    assert "Nano Cerámica" in answer
    assert "98%" in answer


def test_canonical_privacidad_diurna():
    """Test canonical answer for daytime privacy."""
    answer = find_answer("¿Cuál recomiendan para privacidad?")
    assert answer is not None
    assert "Económica" in answer or "Silver Espejo" in answer


def test_canonical_privacidad_24_7():
    """Test canonical answer for 24/7 privacy."""
    answer = find_answer("¿La privacidad funciona de día y de noche?")
    assert answer is not None
    assert "No en películas de control solar" in answer or "Sand Blasting" in answer


def test_canonical_nano_transparente_calor():
    """Test canonical answer for nano transparent heat reduction."""
    answer = find_answer("¿La Nano Cerámica transparente reduce menos calor?")
    assert answer is not None
    # The canonical answer is "No. En esta línea el desempeño térmico proviene de la tecnología nanocerámica, no del nivel de tinte."
    assert "tecnología nanocerámica" in answer or "No" in answer


def test_canonical_efecto_espejo():
    """Test canonical answer for mirror effect."""
    answer = find_answer("¿La Nano Cerámica tiene efecto espejo?")
    assert answer is not None
    assert "No" in answer


def test_canonical_precio_metro_cuadrado():
    """Test canonical answer for price per square meter."""
    answer = find_answer("¿Cuál es el precio por metro cuadrado?")
    assert answer is not None
    assert "Depende" in answer


def test_canonical_no_tengo_medidas():
    """Test canonical answer for no measurements."""
    answer = find_answer("No tengo medidas, ¿qué hago?")
    assert answer is not None
    assert "fotografías" in answer.lower()


def test_canonical_minimo_instalacion():
    """Test canonical answer for minimum installation."""
    answer = find_answer("¿Cuál es el mínimo de instalación?")
    assert answer is not None
    assert "4 m²" in answer


def test_canonical_instalacion_dentro_fuera():
    """Test canonical answer for inside/outside installation."""
    answer = find_answer("¿Se instala por dentro o por fuera?")
    assert answer is not None
    assert "interior" in answer.lower()


def test_canonical_limpieza():
    """Test canonical answer for cleaning."""
    answer = find_answer("¿Cómo se limpia?")
    assert answer is not None
    assert "microfibra" in answer.lower()


def test_canonical_garantia_general():
    """Test canonical answer for general warranty."""
    answer = find_answer("¿Cuánta garantía tienen?")
    assert answer is not None
    assert "5" in answer or "12" in answer


def test_canonical_formas_pago():
    """Test canonical answer for payment methods."""
    answer = find_answer("¿Qué formas de pago aceptan?")
    assert answer is not None
    assert "transferencia" in answer.lower() or "sinpe" in answer.lower()


def test_canonical_trabajan_3m():
    """Test canonical answer for 3M question."""
    answer = find_answer("¿Trabajan con 3M?")
    assert answer is not None
    assert "Actualmente no" in answer


def test_canonical_afecta_wifi():
    """Test canonical answer for WiFi interference."""
    answer = find_answer("¿Afecta Wi‑Fi?")
    assert answer is not None
    assert "No" in answer


def test_canonical_afecta_celular():
    """Test canonical answer for cellular interference."""
    answer = find_answer("¿Afecta celular?")
    assert answer is not None
    assert "No" in answer


def test_canonical_policarbonato():
    """Test canonical answer for polycarbonate."""
    answer = find_answer("¿Se instala sobre policarbonato?")
    assert answer is not None
    assert "sin garantía" in answer.lower()


def test_canonical_vidrio_laminado():
    """Test canonical answer for laminated glass."""
    answer = find_answer("¿Se instala sobre vidrio laminado?")
    assert answer is not None
    assert "Sí" in answer


def test_canonical_vidrio_temperado():
    """Test canonical answer for tempered glass."""
    answer = find_answer("¿Se instala sobre vidrio temperado?")
    assert answer is not None
    assert "Sí" in answer


def test_pending_confirmation_horario():
    """Test pending confirmation for schedule."""
    answer = find_answer("¿Cuál es el horario?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_telefono():
    """Test pending confirmation for phone."""
    answer = find_answer("¿Cuál es el teléfono?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_whatsapp():
    """Test pending confirmation for WhatsApp."""
    answer = find_answer("¿Cuál es el WhatsApp?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_correo():
    """Test pending confirmation for email."""
    answer = find_answer("¿Cuál es el correo?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_redes_sociales():
    """Test pending confirmation for social media."""
    answer = find_answer("¿Cuáles son las redes sociales?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_financiamiento():
    """Test pending confirmation for financing."""
    answer = find_answer("¿Tienen financiamiento?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_costo_visita():
    """Test pending confirmation for visit cost."""
    answer = find_answer("¿Cuál es el costo de la visita tecnica?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_devolucion():
    """Test pending confirmation for returns."""
    answer = find_answer("¿Hacen devoluciones?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_pending_confirmation_cancelacion():
    """Test pending confirmation for cancellations."""
    answer = find_answer("¿Cuál es la política de cancelación?")
    assert answer is not None
    assert "Información pendiente de confirmar" in answer


def test_silver_espejo_warranty_protection():
    """Test Silver Espejo warranty protection."""
    answer = find_answer("¿Cuál es la garantía de Silver Espejo?")
    assert answer is not None
    assert "debe confirmarse" in answer.lower()


def test_silver_espejo_warranty_protection_variant():
    """Test Silver Espejo warranty protection with different wording."""
    answer = find_answer("¿Cuántos años de garantía tiene Silver Espejo?")
    assert answer is not None
    assert "debe confirmarse" in answer.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
