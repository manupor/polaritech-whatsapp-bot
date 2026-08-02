from src.services.faq_service import find_answer


def test_faq_heat_recommendation():
    """FAQ #2: ¿Cuál recomiendan si hace mucho calor? → Nano Cerámica"""
    result = find_answer("¿Cuál recomiendan si hace mucho calor?")
    assert result is not None
    assert "nano cerámica" in result.lower() or "nanocerámica" in result.lower()


def test_faq_privacy_recommendation():
    """FAQ #4: ¿Cuál recomiendan para privacidad?"""
    result = find_answer("¿Cuál recomiendan para privacidad?")
    assert result is not None
    assert "económica" in result.lower() or "sand blasting" in result.lower()


def test_faq_cleaning():
    """FAQ #26: ¿Cómo se limpia?"""
    result = find_answer("¿Cómo se limpia la película?")
    assert result is not None
    assert "microfibra" in result.lower()


def test_faq_warranty_years():
    """FAQ #37: ¿Cuánta garantía tienen?"""
    result = find_answer("¿Cuánta garantía tienen?")
    assert result is not None
    assert "5" in result and "12" in result


def test_faq_payment_methods():
    """FAQ #39: ¿Qué formas de pago aceptan?"""
    result = find_answer("¿Qué formas de pago aceptan?")
    assert result is not None
    assert "sinpe" in result.lower()


def test_product_nano_ceramica():
    """Product match: Nano Cerámica should return structured info"""
    result = find_answer("Información sobre Nano Cerámica")
    assert result is not None
    assert "nano cerámica" in result.lower() or "nanocerámica" in result.lower()


def test_product_sand_blasting():
    result = find_answer("¿Qué es Sand Blasting?")
    assert result is not None
    assert "sand blasting" in result.lower()


def test_no_match():
    result = find_answer("receta de pastel de chocolate con fresas")
    assert result is None


def test_3m_question():
    """FAQ #46: ¿Trabajan con 3M?"""
    result = find_answer("¿Trabajan con 3M?")
    assert result is not None
    assert "actualmente no" in result.lower() or "no" in result.lower()
