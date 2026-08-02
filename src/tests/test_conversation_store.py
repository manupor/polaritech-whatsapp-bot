from src.state.conversation_store import ConversationStore, FlowState


# ── Turn management ──────────────────────────────────────────────────────────

def test_add_and_retrieve():
    store = ConversationStore()
    store.add_turn("+1", "user", "Hello")
    store.add_turn("+1", "bot", "Hi there")

    history = store.get_history("+1")
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].text == "Hi there"


def test_turn_count():
    store = ConversationStore()
    store.add_turn("+1", "user", "A")
    store.add_turn("+1", "bot", "B")
    assert store.turn_count("+1") == 2
    assert store.turn_count("+9999") == 0


def test_clear():
    store = ConversationStore()
    store.add_turn("+1", "user", "A")
    store.set_flow("+1", "quote")
    store.clear("+1")
    assert store.turn_count("+1") == 0
    assert store.get_flow("+1").flow_type == ""


def test_max_turns_trimming():
    store = ConversationStore(max_turns=3)
    for i in range(5):
        store.add_turn("+1", "user", f"msg-{i}")

    history = store.get_history("+1")
    assert len(history) == 3
    assert history[0].text == "msg-2"


# ── Flow state management ───────────────────────────────────────────────────

def test_set_flow_starts_new():
    store = ConversationStore()
    flow = store.set_flow("+1", "quote")
    assert flow.flow_type == "quote"
    assert flow.collected == {}


def test_set_flow_preserves_same_type():
    store = ConversationStore()
    flow = store.set_flow("+1", "quote")
    flow.merge({"provincia": "Heredia"})
    flow2 = store.set_flow("+1", "quote")
    assert flow2.collected["provincia"] == "Heredia"


def test_set_flow_resets_on_type_change():
    store = ConversationStore()
    flow = store.set_flow("+1", "quote")
    flow.merge({"provincia": "Heredia"})
    flow2 = store.set_flow("+1", "warranty")
    assert flow2.flow_type == "warranty"
    assert flow2.collected == {}


def test_merge_does_not_overwrite():
    flow = FlowState(flow_type="quote")
    flow.merge({"provincia": "San José"})
    flow.merge({"provincia": "Alajuela", "zona": "Centro"})
    # Should overwrite provincia since new value is non-blank
    assert flow.collected["provincia"] == "Alajuela"
    assert flow.collected["zona"] == "Centro"


def test_merge_ignores_blank():
    flow = FlowState(flow_type="quote")
    flow.merge({"provincia": "San José"})
    flow.merge({"provincia": "  ", "zona": ""})
    assert flow.collected["provincia"] == "San José"
    assert "zona" not in flow.collected


def test_update_flow_merges():
    store = ConversationStore()
    store.set_flow("+1", "quote")
    store.update_flow("+1", {"provincia": "Heredia"})
    store.update_flow("+1", {"zona": "Santo Domingo"})
    flow = store.get_flow("+1")
    assert flow.collected["provincia"] == "Heredia"
    assert flow.collected["zona"] == "Santo Domingo"


def test_clear_flow_only():
    store = ConversationStore()
    store.add_turn("+1", "user", "Hello")
    store.set_flow("+1", "quote")
    store.clear_flow("+1")
    assert store.turn_count("+1") == 1
    assert store.get_flow("+1").flow_type == ""


# ── Quote readiness ──────────────────────────────────────────────────────────

def test_quote_missing_all():
    flow = FlowState(flow_type="quote")
    missing = flow.quote_missing()
    assert len(missing) == 5
    assert "fotografias" in missing
    assert "medidas" in missing
    assert "provincia" in missing
    assert "zona" in missing
    assert "necesidad" in missing


def test_quote_ready_with_all_fields():
    flow = FlowState(flow_type="quote")
    flow.merge({
        "fotografias": "sí",
        "medidas": "2x3",
        "provincia": "San José",
        "zona": "Escazú",
        "necesidad": "calor",
    })
    assert flow.quote_ready() is True
    assert flow.quote_missing() == []


def test_quote_ready_no_measurements():
    flow = FlowState(flow_type="quote")
    flow.no_measurements = True
    flow.merge({
        "fotografias": "sí",
        "provincia": "San José",
        "zona": "Escazú",
        "necesidad": "calor",
    })
    assert flow.quote_ready() is True


def test_quote_not_ready_partial():
    flow = FlowState(flow_type="quote")
    flow.merge({"provincia": "Heredia", "necesidad": "calor"})
    assert flow.quote_ready() is False
    missing = flow.quote_missing()
    assert "fotografias" in missing
    assert "medidas" in missing
    assert "zona" in missing


# ── Warranty readiness ───────────────────────────────────────────────────────

def test_warranty_missing_all():
    flow = FlowState(flow_type="warranty")
    missing = flow.warranty_missing()
    assert len(missing) == 4
    assert "fotografias" in missing
    assert "fecha_instalacion" in missing
    assert "producto" in missing
    assert "descripcion" in missing


def test_warranty_ready():
    flow = FlowState(flow_type="warranty")
    flow.merge({
        "fotografias": "sí",
        "fecha_instalacion": "enero 2024",
        "producto": "Nano Cerámica",
        "descripcion": "se despegó una esquina",
    })
    assert flow.warranty_ready() is True


# ── Visit readiness ─────────────────────────────────────────────────────────

def test_visit_missing_all():
    flow = FlowState(flow_type="visit")
    missing = flow.visit_missing()
    assert len(missing) == 4


def test_visit_ready():
    flow = FlowState(flow_type="visit")
    flow.merge({
        "provincia": "Heredia",
        "zona": "Santo Domingo",
        "fotografias": "sí",
        "objetivo": "cotizar ventanas",
    })
    assert flow.visit_ready() is True
