"""
Tests for brand-related intent detection (brand_3m, brand_general, competitor_cheaper_3m, competitor_comparison).
"""

import pytest
from src.services.faq_service import find_answer


def test_brand_3m_exact():
    """Test exact 3M question returns brand_3m answer."""
    answer = find_answer("¿Trabajan con 3M?")
    assert answer is not None
    assert "Actualmente no" in answer
    assert "Polaritech trabaja con tecnologías seleccionadas" in answer


def test_brand_3m_variant_usan():
    """Test 3M question with 'usan' variant."""
    answer = find_answer("¿Usan 3M?")
    assert answer is not None
    assert "Actualmente no" in answer


def test_brand_3m_variant_tienen():
    """Test 3M question with 'tienen' variant."""
    answer = find_answer("¿Tienen 3M?")
    assert answer is not None
    assert "Actualmente no" in answer


def test_brand_3m_variant_manejan():
    """Test 3M question with 'manejan' variant."""
    answer = find_answer("¿Manejan 3M?")
    assert answer is not None
    assert "Actualmente no" in answer


def test_brand_3m_variant_ofrecen():
    """Test 3M question with 'ofrecen' variant."""
    answer = find_answer("¿Ofrecen 3M?")
    assert answer is not None
    assert "Actualmente no" in answer


def test_brand_general_que_marcas():
    """Test general brand question returns brand_general answer."""
    answer = find_answer("¿Qué marcas trabajan?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer
    assert "Polaritech trabaja con tecnologías seleccionadas" in answer


def test_brand_general_con_cual_marca():
    """Test general brand question with 'con cual marca' variant."""
    answer = find_answer("¿Con cuál marca trabajan?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer


def test_brand_general_cuales_marcas():
    """Test general brand question with 'cuales marcas' variant."""
    answer = find_answer("¿Cuáles marcas manejan?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer


def test_brand_general_que_marca_usan():
    """Test general brand question with 'que marca usan' variant."""
    answer = find_answer("¿Qué marca usan?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer


def test_brand_general_manejan_alguna():
    """Test general brand question with 'manejan alguna' variant."""
    answer = find_answer("¿Manejan alguna marca específica?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer


def test_brand_general_trabajan_alguna():
    """Test general brand question with 'trabajan con alguna' variant."""
    answer = find_answer("¿Trabajan con alguna marca?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer


def test_brand_general_usan_alguna():
    """Test general brand question with 'usan alguna' variant."""
    answer = find_answer("¿Usan alguna marca?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer


def test_brand_general_marca_laminas():
    """Test general brand question with 'marca de las laminas' variant."""
    answer = find_answer("¿Cuál es la marca de las láminas?")
    assert answer is not None
    assert "Actualmente no trabajamos con 3M" in answer


def test_brand_general_includes_orientation():
    """Test brand_general answer includes orientation offer."""
    answer = find_answer("¿Qué marcas trabajan?")
    assert answer is not None
    assert "calor" in answer.lower() or "privacidad" in answer.lower() or "seguridad" in answer.lower()


def test_competitor_cheaper_3m_exact():
    """Test competitor cheaper 3M question returns correct answer."""
    answer = find_answer("Me ofrecieron 3M más barato")
    assert answer is not None
    assert "comparar tecnología" in answer.lower()
    assert "desempeño" in answer.lower()


def test_competitor_cheaper_3m_variant():
    """Test competitor cheaper 3M with 'otra empresa' variant."""
    answer = find_answer("Otra empresa me ofrece 3M más barato")
    assert answer is not None
    assert "comparar tecnología" in answer.lower()


def test_competitor_cheaper_3m_short():
    """Test competitor cheaper 3M with short variant."""
    answer = find_answer("3M más barato")
    assert answer is not None
    assert "comparar tecnología" in answer.lower()


def test_brand_general_not_price_comparison():
    """Test brand_general never returns price comparison response."""
    answer = find_answer("¿Qué marcas trabajan?")
    assert answer is not None
    # Should NOT contain price comparison language
    assert "barato" not in answer.lower()
    assert "precio" not in answer.lower() or "comparar" not in answer.lower()


def test_brand_general_not_competitor_cheaper():
    """Test brand_general never returns competitor_cheaper_3m response."""
    answer = find_answer("¿Con cuál marca trabajan?")
    assert answer is not None
    # Should NOT be the competitor cheaper response
    assert not (answer.startswith("Es posible") and "comparar tecnología" in answer.lower())


def test_competitor_comparison():
    """Test competitor comparison question."""
    answer = find_answer("¿Por qué ustedes y no otra marca?")
    assert answer is not None
    assert "respeto" in answer.lower() or "tecnología" in answer.lower()


def test_competitor_comparison_variant():
    """Test competitor comparison with 'diferencia' variant."""
    answer = find_answer("¿Qué diferencia tienen con otras marcas?")
    assert answer is not None
    assert "respeto" in answer.lower() or "tecnología" in answer.lower()


def test_brand_3m_priority_over_general():
    """Test brand_3m is detected before brand_general."""
    answer = find_answer("¿Trabajan con 3M?")
    assert answer is not None
    # Should be the specific 3M answer, not the general brand answer
    assert "Actualmente no" in answer
    # Should NOT include the orientation phrase from brand_general
    assert "calor" not in answer.lower() or "privacidad" not in answer.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
