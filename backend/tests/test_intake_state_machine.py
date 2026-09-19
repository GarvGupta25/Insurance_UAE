from types import SimpleNamespace

from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import agents
from app.models import Recommendation

ANSWERS = {
    "legal_name": "Mina Example",
    "date_of_birth": "1990-01-02",
    "nationality": "Emirati",
    "residency": "citizen",
    "emirate": "Dubai",
    "emirates_id_status": "issued",
    "diagnosed_conditions": "yes",
    "smoker": "no",
    "maternity": True,
    "geography": "UAE",
    "start_date": "2026-10-01",
    "near_term_needs": ["maternity within 12 months"],
    "maximum_maternity_wait": 6,
    "conditions": ["managed diabetes"],
    "immediate_chronic_cover": True,
    "payer": "employer",
    "annual_budget": 18000,
    "strict_budget": False,
    "payment_frequency": "annual",
    "company_name": "Fictional Demo LLC",
    "contribution_aed": 5000,
}

EXPECTED_SEQUENCE = agents.intake_sequence(ANSWERS)


def configure_intake(monkeypatch, *, extraction=None):
    asked = []
    extracted = []
    monkeypatch.setattr(
        agents,
        "settings",
        lambda: SimpleNamespace(groq_api_key="test", groq_model="test"),
    )

    def phrase(field, _facts, *, clarification=False):
        asked.append((field, clarification))
        return f"ASK {field}"

    def extract(field, text, _facts):
        extracted.append(field)
        if extraction:
            return extraction(field, text)
        return ANSWERS[field]

    monkeypatch.setattr(agents, "phrase_intake_question", phrase)
    monkeypatch.setattr(agents, "extract_intake_value", extract)
    monkeypatch.setattr(agents, "summarize_intake", lambda _facts: "PROFILE COMPLETE.")
    return asked, extracted


def start_graph(checkpointer=None, thread_id="intake-test"):
    compiled = agents.graph(checkpointer)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 64}
    state = compiled.invoke({"text": "start", "facts": {}, "context": {}}, config)
    return compiled, config, state


def answer_until_confirmation(compiled, config, state):
    while state["stage"] == "collecting":
        state = compiled.invoke(
            {"text": f"answer for {state['current_node']}", "facts": {}, "context": {}},
            config,
        )
    return state


def test_full_linear_intake_answers_every_applicable_field_once(monkeypatch):
    asked, extracted = configure_intake(monkeypatch)
    compiled, config, state = start_graph(MemorySaver(), "full-linear")
    state = answer_until_confirmation(compiled, config, state)

    assert state["stage"] == "complete_pending_confirmation"
    assert state["current_node"] == "intake_complete"
    assert [field for field, clarification in asked if not clarification] == EXPECTED_SEQUENCE
    assert extracted == EXPECTED_SEQUENCE
    assert all(state["intake_fields"][field]["answered"] for field in EXPECTED_SEQUENCE)
    assert len(set(extracted)) == len(EXPECTED_SEQUENCE)

    state = compiled.invoke({"text": "yes", "facts": {}, "context": {}}, config)
    assert state["stage"] == "confirmed_for_review"
    assert state["result"]["ready_for_broker_review"] is True


def test_interrupted_intake_resumes_at_fourth_field(monkeypatch):
    asked, extracted = configure_intake(monkeypatch)
    saver = MemorySaver()
    compiled, config, state = start_graph(saver, "resume")

    for _ in range(3):
        state = compiled.invoke(
            {"text": f"answer for {state['current_node']}", "facts": {}, "context": {}},
            config,
        )

    assert state["current_node"] == EXPECTED_SEQUENCE[3]
    assert [field for field, clarification in asked if not clarification] == EXPECTED_SEQUENCE[:4]

    resumed = agents.graph(saver)
    state = resumed.invoke(
        {"text": f"answer for {state['current_node']}", "facts": {}, "context": {}},
        config,
    )
    assert state["current_node"] == EXPECTED_SEQUENCE[4]
    assert extracted == EXPECTED_SEQUENCE[:4]
    assert asked.count((EXPECTED_SEQUENCE[0], False)) == 1


def test_unusable_answer_reasks_same_question_without_advancing(monkeypatch):
    attempts = {"legal_name": 0}

    def extraction(field, _text):
        attempts[field] = attempts.get(field, 0) + 1
        if field == "legal_name" and attempts[field] == 1:
            return agents.NEEDS_CLARIFICATION
        return ANSWERS[field]

    asked, _ = configure_intake(monkeypatch, extraction=extraction)
    compiled, config, state = start_graph(MemorySaver(), "clarify")
    state = compiled.invoke({"text": "I do not know what you mean", "facts": {}, "context": {}}, config)

    assert state["current_node"] == "legal_name"
    assert state["intake_fields"]["legal_name"]["answered"] is False
    assert asked == [("legal_name", False), ("legal_name", True)]

    state = compiled.invoke({"text": "Mina Example", "facts": {}, "context": {}}, config)
    assert state["current_node"] == "date_of_birth"
    assert state["intake_fields"]["legal_name"] == {
        "value": "Mina Example",
        "answered": True,
    }


def test_completion_no_pauses_without_finalizing_recommendation(fixture_client, monkeypatch):
    _, _, engine = fixture_client
    configure_intake(monkeypatch)
    compiled, config, state = start_graph(MemorySaver(), "pause")
    state = answer_until_confirmation(compiled, config, state)
    state = compiled.invoke({"text": "no", "facts": {}, "context": {}}, config)

    assert state["stage"] == "paused"
    assert state["result"]["ready_for_broker_review"] is False
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Recommendation)) == 0
