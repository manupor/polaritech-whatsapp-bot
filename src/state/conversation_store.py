"""
In-memory conversation history and flow state keyed by phone number.
Replace with Redis or a database for production persistence.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set


# ── Required fields for each flow ───────────────────────────────────────────

QUOTE_REQUIRED_FIELDS: Set[str] = {
    "fotografias",
    "medidas",
    "provincia",
    "zona",
    "necesidad",
}

WARRANTY_REQUIRED_FIELDS: Set[str] = {
    "fotografias",
    "fecha_instalacion",
    "producto",
    "descripcion",
}

VISIT_REQUIRED_FIELDS: Set[str] = {
    "provincia",
    "zona",
    "fotografias",
    "objetivo",
}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Turn:
    role: str  # "user" or "bot"
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FlowState:
    """Tracks progressive field collection for a given flow type."""
    flow_type: str = ""  # "quote", "warranty", "visit", or ""
    collected: Dict[str, str] = field(default_factory=dict)
    no_measurements: bool = False

    # ── Merge helpers ────────────────────────────────────────────────────

    def merge(self, updates: Dict[str, str]) -> None:
        """Merge new field values without overwriting existing ones unless blank."""
        for key, value in updates.items():
            if value and value.strip():
                self.collected[key] = value.strip()

    # ── Quote helpers ────────────────────────────────────────────────────

    def quote_missing(self) -> List[str]:
        if self.no_measurements:
            required = QUOTE_REQUIRED_FIELDS - {"medidas"}
        else:
            required = QUOTE_REQUIRED_FIELDS
        return sorted(required - set(self.collected.keys()))

    def quote_ready(self) -> bool:
        return len(self.quote_missing()) == 0

    # ── Warranty helpers ─────────────────────────────────────────────────

    def warranty_missing(self) -> List[str]:
        return sorted(WARRANTY_REQUIRED_FIELDS - set(self.collected.keys()))

    def warranty_ready(self) -> bool:
        return len(self.warranty_missing()) == 0

    # ── Visit helpers ────────────────────────────────────────────────────

    def visit_missing(self) -> List[str]:
        return sorted(VISIT_REQUIRED_FIELDS - set(self.collected.keys()))

    def visit_ready(self) -> bool:
        return len(self.visit_missing()) == 0


# ── Store ────────────────────────────────────────────────────────────────────

class ConversationStore:
    def __init__(self, max_turns: int = 50) -> None:
        self._turns: Dict[str, List[Turn]] = {}
        self._flows: Dict[str, FlowState] = {}
        self._max_turns = max_turns

    # ── Turn management ──────────────────────────────────────────────────

    def add_turn(self, phone: str, role: str, text: str) -> None:
        history = self._turns.setdefault(phone, [])
        history.append(Turn(role=role, text=text))
        if len(history) > self._max_turns:
            self._turns[phone] = history[-self._max_turns:]

    def get_history(self, phone: str) -> List[Turn]:
        return list(self._turns.get(phone, []))

    def turn_count(self, phone: str) -> int:
        return len(self._turns.get(phone, []))

    # ── Flow state management ────────────────────────────────────────────

    def get_flow(self, phone: str) -> FlowState:
        if phone not in self._flows:
            self._flows[phone] = FlowState()
        return self._flows[phone]

    def set_flow(self, phone: str, flow_type: str) -> FlowState:
        """Start or continue a flow. Preserves existing data if same type."""
        flow = self.get_flow(phone)
        if flow.flow_type != flow_type:
            self._flows[phone] = FlowState(flow_type=flow_type)
        else:
            flow.flow_type = flow_type
        return self._flows[phone]

    def update_flow(self, phone: str, fields: Dict[str, str]) -> FlowState:
        """Merge fields into the current flow without overwriting."""
        flow = self.get_flow(phone)
        flow.merge(fields)
        return flow

    # ── Cleanup ──────────────────────────────────────────────────────────

    def clear(self, phone: str) -> None:
        self._turns.pop(phone, None)
        self._flows.pop(phone, None)

    def clear_flow(self, phone: str) -> None:
        self._flows.pop(phone, None)


# Singleton instance
conversation_store = ConversationStore()
