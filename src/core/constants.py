"""
Centralized business rules, intent keywords, reply templates, and product
mapping for Polaritech Window Film.

Source of truth: Polaritech_FAQ_v1-3-1-1.json / Polaritech_Base_Conocimiento_v1-2.md
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum
from typing import Dict, FrozenSet, List, Optional


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


# ── Text normalization ────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """
    Normalize text for intent matching:
    - lowercase
    - trim
    - remove accents/tildes
    - collapse multiple spaces
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remove accents (normalize to NFD and remove combining marks)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    
    # Trim
    text = text.strip()
    
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text


# ── Stable menu button IDs ────────────────────────────────────────────────────

MENU_ID_PRODUCTS = "menu_products"
MENU_ID_QUOTE = "menu_quote"
MENU_ID_VISIT = "menu_visit"
MENU_ID_HUMAN = "menu_human"

# Map button IDs directly to intents (bypass classifier)
BUTTON_ID_TO_INTENT: Dict[str, Intent] = {
    MENU_ID_PRODUCTS: Intent.PRODUCT_INFO,
    MENU_ID_QUOTE: Intent.QUOTE_REQUEST,
    MENU_ID_VISIT: Intent.TECHNICAL_VISIT,
    MENU_ID_HUMAN: Intent.ESCALATE,
}

# Text aliases for normalized text matching (bypass classifier)
TEXT_ALIASES: Dict[str, Intent] = {
    # Quote aliases
    "cotizacion": Intent.QUOTE_REQUEST,
    "cotizar": Intent.QUOTE_REQUEST,
    "presupuesto": Intent.QUOTE_REQUEST,
    "precio": Intent.QUOTE_REQUEST,
    "costo": Intent.QUOTE_REQUEST,
    # Product info aliases
    "productos": Intent.PRODUCT_INFO,
    "info de productos": Intent.PRODUCT_INFO,
    "informacion de productos": Intent.PRODUCT_INFO,
    "laminas": Intent.PRODUCT_INFO,
    "lamina": Intent.PRODUCT_INFO,
    "pelicula": Intent.PRODUCT_INFO,
    "catalogo": Intent.PRODUCT_INFO,
    # Visit aliases
    "agendar visita": Intent.TECHNICAL_VISIT,
    "visita tecnica": Intent.TECHNICAL_VISIT,
    "visita": Intent.TECHNICAL_VISIT,
    # Human/escalation aliases
    "asesor": Intent.ESCALATE,
    "humano": Intent.ESCALATE,
    "hablar con asesor": Intent.ESCALATE,
    "persona real": Intent.ESCALATE,
}


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
        "producto", "productos", "catálogo", "catalogo",
        "info de productos", "información de productos",
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

# ── Quick-reply buttons ─────────────────────────────────────────────────────
# WhatsApp reply buttons: max 3 per message, title max 20 characters.

BTN_PRODUCTOS = {"id": MENU_ID_PRODUCTS, "title": "Info de productos"}
BTN_COTIZACION = {"id": MENU_ID_QUOTE, "title": "Cotización"}
BTN_VISITA = {"id": MENU_ID_VISIT, "title": "Agendar visita"}
BTN_ASESOR = {"id": MENU_ID_HUMAN, "title": "Hablar con asesor"}
BTN_SIN_MEDIDAS = {"id": "quote_sin_medidas", "title": "No tengo medidas"}

# Fallback offered whenever an intent has no specific set
DEFAULT_BUTTONS: List[Dict[str, str]] = [BTN_PRODUCTOS, BTN_COTIZACION, BTN_VISITA]

INTENT_BUTTONS: Dict[Intent, List[Dict[str, str]]] = {
    Intent.GREETING: [BTN_PRODUCTOS, BTN_COTIZACION, BTN_VISITA],
    Intent.UNKNOWN: [BTN_PRODUCTOS, BTN_COTIZACION, BTN_ASESOR],
    Intent.FAQ: [BTN_COTIZACION, BTN_PRODUCTOS, BTN_ASESOR],
    Intent.PRODUCT_INFO: [BTN_COTIZACION, BTN_VISITA, BTN_ASESOR],
    Intent.QUOTE_REQUEST: [BTN_SIN_MEDIDAS, BTN_VISITA, BTN_ASESOR],
    Intent.APPOINTMENT: [BTN_COTIZACION, BTN_ASESOR],
    Intent.TECHNICAL_VISIT: [BTN_COTIZACION, BTN_ASESOR],
    Intent.COMPETITOR: [BTN_PRODUCTOS, BTN_COTIZACION, BTN_ASESOR],
    Intent.DISCOUNT: [BTN_COTIZACION, BTN_PRODUCTOS, BTN_ASESOR],
    Intent.PENDING_QUERY: [BTN_ASESOR],
    # Already handed off to a human — no options to avoid confusion
    Intent.ESCALATE: [],
    Intent.WARRANTY_CLAIM: [],
}

# Text sent to the pipeline when a button is tapped (legacy, for compatibility)
BUTTON_ID_TO_TEXT: Dict[str, str] = {
    MENU_ID_PRODUCTS: "Información de productos",
    MENU_ID_QUOTE: "Quiero solicitar una cotización",
    MENU_ID_VISIT: "Necesito una visita técnica",
    MENU_ID_HUMAN: "asesor",
    "quote_sin_medidas": "No tengo medidas",
}

# Prompt used when the reply body is too long to fit in an interactive message
BUTTONS_FOLLOWUP_PROMPT = "¿Cómo desea continuar?"

# WhatsApp interactive body limit
INTERACTIVE_BODY_LIMIT = 1024


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
        "Le saluda Valentina, asistente virtual de Polaritech. 😊\n\n"
        "¿En qué le puedo ayudar?\n"
        "• Información de productos\n"
        "• Cotización\n"
        "• Agendar visita técnica\n\n"
        "O escriba *asesor* para hablar con un miembro del equipo."
    ),
    "unknown": (
        "Disculpe, no estoy segura de haber entendido. Puedo ayudarle con:\n"
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
    "product_catalog": (
        "En Polaritech trabajamos las siguientes líneas de películas arquitectónicas:\n\n"
        "☀️ *Nano Cerámica (IRR98)* — Línea premium 100% nanocerámica, sin metal. "
        "Hasta 98% de rechazo infrarrojo y 99.5% de protección UV, sin efecto espejo "
        "y sin interferir Wi‑Fi. Disponible en 70%, 45%, 20% y 10%. Garantía 12 años.\n\n"
        "💰 *Económica (IRR65)* — Control solar con reducción moderada de calor y "
        "privacidad de día, enfocada en costo-beneficio. Garantía 5 años.\n\n"
        "🪞 *Silver Espejo* — Película reflectiva: efecto espejo de día, alta privacidad "
        "diurna y reducción de deslumbramiento.\n\n"
        "🛡️ *Película de Seguridad* — Refuerza el vidrio y ayuda a mantener unidos los "
        "fragmentos en caso de rotura.\n\n"
        "🔲 *Sand Blasting* — Acabado tipo vidrio esmerilado: privacidad permanente en "
        "ambos sentidos permitiendo el paso de luz natural.\n\n"
        "⬛ *White Out / Black Out* — Para bloqueo visual total o superficies opacas.\n\n"
        "¿Sobre cuál desea más detalle? También puedo recomendarle según su necesidad "
        "principal: calor, privacidad, seguridad o decoración."
    ),
}
