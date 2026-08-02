"""
Centralized business rules, intent keywords, reply templates, and product
mapping for Polaritech Window Film.

Source of truth: Polaritech_FAQ_v1-3-1-1.json / Polaritech_Base_Conocimiento_v1-2.md
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, List


# ── Pending-info sentinel ────────────────────────────────────────────────────

PENDING_PHRASE = "Información pendiente de confirmar"


def pending_fallback() -> str:
    """Return the exact phrase required when data is missing or unconfirmed."""
    return PENDING_PHRASE


# ── Intents ──────────────────────────────────────────────────────────────────

class Intent(str, Enum):
    GREETING = "greeting"
    FAQ = "faq"
    QUOTE_REQUEST = "quote_request"
    APPOINTMENT = "appointment"
    PRODUCT_INFO = "product_info"
    WARRANTY_CLAIM = "warranty_claim"
    TECHNICAL_VISIT = "technical_visit"
    COMPETITOR = "competitor"
    DISCOUNT = "discount"
    PENDING_QUERY = "pending_query"
    ESCALATE = "escalate"
    UNKNOWN = "unknown"


INTENT_KEYWORDS: Dict[Intent, List[str]] = {
    Intent.GREETING: [
        "hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches",
        "buen día", "buen dia", "hello", "hi", "hey",
    ],
    Intent.QUOTE_REQUEST: [
        "cotización", "cotizacion", "precio", "cuánto cuesta", "cuanto cuesta",
        "costo", "presupuesto", "cuánto vale", "cuanto vale",
        "cotizar", "metro cuadrado",
        "quote", "price", "cost", "estimate", "how much",
    ],
    Intent.APPOINTMENT: [
        "cita", "agendar", "programar", "reservar", "fecha",
        "appointment", "schedule", "book",
    ],
    Intent.PRODUCT_INFO: [
        "nano cerámica", "nano ceramica", "nanocerámica", "nanoceramica",
        "económica", "economica", "irr65",
        "silver espejo", "silver grey",
        "película de seguridad", "pelicula de seguridad",
        "sand blasting", "sandblasting",
        "white out", "black out",
        "película", "pelicula", "lámina", "lamina",
        "ceramic", "tint", "film", "uv",
        "calor", "privacidad", "heat", "privacy",
    ],
    Intent.WARRANTY_CLAIM: [
        "reclamo", "defecto", "se despegó", "se despego",
        "se decoloró", "se decoloro", "arruga", "despegando",
        "warranty", "claim", "defect",
    ],
    Intent.TECHNICAL_VISIT: [
        "visita técnica", "visita tecnica",
        "inspección", "inspeccion",
        "revisar el lugar", "ir a ver",
        "technical visit", "inspection",
    ],
    Intent.COMPETITOR: [
        "3m", "llumar", "suntek", "competencia",
        "otra marca", "más barato", "mas barato",
    ],
    Intent.DISCOUNT: [
        "descuento", "rebaja", "promoción", "promocion",
        "discount",
    ],
    Intent.PENDING_QUERY: [
        "financiamiento", "financiar", "cuotas",
        "cancelación", "cancelacion", "devolución", "devolucion", "reembolso",
    ],
    Intent.ESCALATE: [
        "asesor", "persona real", "hablar con alguien", "agente",
        "agent", "human", "representative", "speak to someone",
    ],
}

# ── Escalation triggers ─────────────────────────────────────────────────────
ALWAYS_ESCALATE_INTENTS: FrozenSet[Intent] = frozenset({
    Intent.WARRANTY_CLAIM,
    Intent.TECHNICAL_VISIT,
})

MAX_TURNS_BEFORE_ESCALATION = 10

# ── Product recommendation mapping ──────────────────────────────────────────
NEED_TO_PRODUCT: Dict[str, str] = {
    "calor": "Nano Cerámica / Nanoceramic IRR98",
    "calor fuerte": "Nano Cerámica / Nanoceramic IRR98",
    "mucho calor": "Nano Cerámica / Nanoceramic IRR98",
    "heat": "Nano Cerámica / Nanoceramic IRR98",
    "reducción térmica": "Nano Cerámica / Nanoceramic IRR98",
    "reduccion termica": "Nano Cerámica / Nanoceramic IRR98",
    "privacidad diurna": "IRR65 Economic / Línea Económica",
    "privacidad día": "IRR65 Economic / Línea Económica",
    "privacidad de día": "IRR65 Economic / Línea Económica",
    "privacidad espejo": "Silver Espejo / Silver Grey",
    "efecto espejo": "Silver Espejo / Silver Grey",
    "privacidad permanente": "Sand Blasting",
    "privacidad 24": "Sand Blasting",
    "seguridad": "Película de Seguridad",
    "safety": "Película de Seguridad",
    "fragmentos": "Película de Seguridad",
    "refuerzo": "Película de Seguridad",
    "glass fragment": "Película de Seguridad",
}

# ── Human-readable field labels (Spanish) ────────────────────────────────────
FIELD_LABELS: Dict[str, str] = {
    "fotografias": "📸 Fotografías",
    "medidas": "📏 Medidas aproximadas (alto × ancho)",
    "provincia": "📍 Provincia",
    "zona": "📍 Zona",
    "necesidad": "🎯 Necesidad principal",
    "fecha_instalacion": "📅 Fecha aproximada de instalación",
    "producto": "🏷️ Producto instalado",
    "descripcion": "📝 Descripción del problema",
    "objetivo": "🎯 Objetivo del proyecto",
}

# ── Reply templates ──────────────────────────────────────────────────────────

TEMPLATES: Dict[str, str] = {
    "greeting": (
        "👋 ¡Bienvenido a Polaritech Window Film!\n"
        "Somos especialistas en películas arquitectónicas para control solar, "
        "privacidad, seguridad y decoración de vidrio.\n\n"
        "¿En qué le puedo ayudar?\n"
        "• Información de productos\n"
        "• Cotización\n"
        "• Agendar visita técnica\n\n"
        "O escriba *asesor* para hablar con un miembro del equipo."
    ),
    "unknown": (
        "No estoy seguro de haber entendido. Puedo ayudarle con:\n"
        "• Información sobre películas (Nano Cerámica, Económica, Silver Espejo, "
        "Seguridad, Sand Blasting)\n"
        "• Cotizaciones\n"
        "• Visitas técnicas\n\n"
        "O escriba *asesor* para comunicarse con nuestro equipo."
    ),
    "escalation": (
        "Con gusto le comunico con un asesor de Polaritech. "
        "Alguien se pondrá en contacto con usted en breve. "
        "¡Gracias por su paciencia!"
    ),
    "quote_initial": (
        "¡Con gusto le ayudo con una cotización!\n\n"
        "En Polaritech las cotizaciones son personalizadas — no manejamos un precio "
        "fijo por metro cuadrado ya que depende de varios factores del proyecto.\n\n"
        "Para darle una estimación precisa, necesito:\n"
        "1. 📸 Fotografías de las ventanas\n"
        "2. 📏 Medidas aproximadas (alto × ancho)\n"
        "3. 📍 Provincia y zona\n"
        "4. 🎯 Necesidad principal (calor, privacidad, seguridad, decoración)\n\n"
        "Si no tiene medidas exactas, con las fotografías y ubicación puedo hacer una "
        "estimación preliminar. Las medidas finales se rectifican el día de la instalación."
    ),
    "quote_no_measurements": (
        "¡Sin problema! Con las fotografías y su ubicación podemos hacer una "
        "estimación preliminar.\n"
        "Las medidas finales se confirman el día de la instalación."
    ),
    "quote_handoff": (
        "¡Gracias por la información! Con estos datos un asesor de Polaritech "
        "preparará su cotización formal y se comunicará con usted.\n\n"
        "Recuerde que el mínimo de instalación dentro del GAM es de 4 m².\n"
        "La reserva se confirma con 50%% de adelanto y 50%% al finalizar."
    ),
    "price_per_meter": (
        "En Polaritech no manejamos un precio fijo por metro cuadrado.\n\n"
        "La cotización es personalizada y depende de: metros cuadrados, línea "
        "seleccionada, ubicación, dificultad de acceso, necesidad de andamios y "
        "condiciones del proyecto.\n\n"
        "Si desea, puedo iniciar el proceso de cotización. Solo necesito:\n"
        "📸 Fotografías, 📏 medidas aproximadas, 📍 provincia y zona, "
        "🎯 necesidad principal."
    ),
    "appointment": (
        "¡Excelente! Para coordinar una cita:\n"
        "1. 📍 Provincia y zona\n"
        "2. 📸 Fotografías de las ventanas\n"
        "3. 📏 Medidas aproximadas si las tiene\n"
        "4. 🎯 Objetivo del proyecto\n\n"
        "La reserva se confirma con 50%% de adelanto y 50%% al finalizar."
    ),
    "warranty_claim": (
        "Lamento escuchar eso. Los reclamos de garantía son atendidos directamente "
        "por un asesor de Polaritech.\n\n"
        "Para agilizar el proceso, le pido:\n"
        "1. 📸 Fotografías del problema\n"
        "2. 📅 Fecha aproximada de instalación\n"
        "3. 🏷️ Producto instalado\n"
        "4. 📝 Descripción del problema\n\n"
        "Un asesor se comunicará con usted en breve."
    ),
    "technical_visit": (
        "Las visitas técnicas se coordinan principalmente dentro del Gran Área "
        "Metropolitana (GAM) y se consideran para proyectos de aproximadamente "
        "7 m² o más, o cuando la complejidad lo requiera.\n\n"
        "Para programar, necesito:\n"
        "1. 📍 Provincia y zona\n"
        "2. 📸 Fotografías\n"
        "3. 📏 Medidas aproximadas si existen\n"
        "4. 🎯 Objetivo del proyecto\n\n"
        "Un asesor confirmará la disponibilidad."
    ),
    "competitor_3m": (
        "Actualmente Polaritech no trabaja con 3M. Trabajamos con tecnologías "
        "seleccionadas por su equilibrio entre desempeño, calidad y costo.\n\n"
        "Le recomendamos comparar tecnología, desempeño, garantía e instalación, "
        "no solo la marca."
    ),
    "competitor_cheaper": (
        "Es posible que encuentre opciones a menor precio. Existen distintas "
        "tecnologías, garantías y niveles de instalación en el mercado.\n\n"
        "Le recomendamos comparar el desempeño total del producto, la garantía "
        "y la calidad de la instalación — no solo el precio."
    ),
    "discount": (
        "Entiendo su consulta. En Polaritech podemos revisar si existe una "
        "alternativa dentro de su presupuesto sin comprometer la calidad.\n\n"
        "No podemos prometer descuentos sin autorización, pero con gusto "
        "un asesor puede evaluar opciones para su proyecto."
    ),
    "pending_generic": (
        "{pending}\n\n"
        "Un asesor de Polaritech podrá brindarle esta información directamente."
    ),
    "fallback_no_match": (
        "No tengo información específica sobre eso en este momento.\n\n"
        "{pending}\n\n"
        "Puedo comunicarle con un asesor. Escriba *asesor* en cualquier momento."
    ),
    "pending_info": PENDING_PHRASE,
    "night_privacy": (
        "Las películas de control solar ofrecen privacidad durante el día gracias "
        "a la diferencia de iluminación. De noche, con luces interiores encendidas, "
        "el efecto se invierte.\n\n"
        "Para privacidad permanente (24/7) recomendamos:\n"
        "• *Sand Blasting* — acabado tipo vidrio esmerilado\n"
        "• Cortinas o persianas como complemento"
    ),
}
