from uuid import uuid4

from sqlalchemy.orm import Session
from test_phase_one import facts, send, setup_case

from app.agents import interpret
from app.auth import User
from app.domain import compare
from app.financial import financial_scenario
from app.models import Message


def scenario(quote, **changes):
    values = {"monthly_budget_aed": 1000, "outpatient_spend_aed": 0, "contribution_aed": 0, "priority": "balanced"}
    return financial_scenario(quote, **(values | changes))


def test_scenario_changes_preference_but_never_overrides_known_coverage_gaps():
    quote = {"items": compare(facts())}
    cheap = scenario(quote, priority="lower_premium")
    assert cheap["recommended_plan_id"] == "plan_a"
    high_care = scenario(quote, monthly_budget_aed=2000, outpatient_spend_aed=10000,
                         priority="lower_member_cost")
    assert high_care["recommended_plan_id"] == "plan_c"
    assert high_care["rows"][0]["premium_fils"] == 420000
    assert high_care["rows"][0]["member_premium_fils"] == 420000
    assert high_care["rows"][0]["illustrative_member_care_fils"] == 405000
    maternity = scenario({"items": compare(facts(maternity=True, maximum_maternity_wait=6))},
                         monthly_budget_aed=0, priority="lower_premium")
    assert maternity["recommended_plan_id"] == "plan_c"
    assert "No supported plan is within" in maternity["reply"]


def test_financial_agent_uses_quote_tool_for_explicit_budget_and_tradeoff():
    quote = {"items": compare(facts())}
    result = interpret({"text": "My monthly budget is AED 2000, and I want lower out of pocket cost.",
                        "facts": facts(), "context": {"quote": quote}})["result"]
    assert result["mode"] == "financial_guided"
    assert result["financial_inputs"]["monthly_budget_aed"] == 2000
    assert result["financial_inputs"]["priority"] == "lower_member_cost"
    assert result["financial_result"]["recommended_plan_id"] == "plan_c"
    assert result["patch"] == {}


def test_scenario_is_saved_by_quote_owner_and_rejects_stale_quote(fixture_client):
    client, owner, engine = fixture_client
    case, quote = setup_case(client)
    body = {"monthly_budget_aed": 1200, "outpatient_spend_aed": 3000,
            "contribution_aed": 1500, "priority": "balanced"}
    key = str(uuid4())
    first = send(client, f"/api/quotes/{quote}/financial-scenarios", body, key)
    assert first.status_code == 200, first.text
    preview = send(client, f"/api/quotes/{quote}/financial-preview", body)
    assert preview.status_code == 200 and preview.json() == first.json()["result"]
    assert send(client, f"/api/quotes/{quote}/financial-scenarios", body, key).json() == first.json()
    saved = client.get(f"/api/quotes/{quote}/financial-scenarios").json()["items"]
    assert len(saved) == 1 and saved[0]["inputs"] == body
    queued = send(client, f"/api/cases/{case}/messages", {"text": "Compare my budget", "quote_id": quote})
    assert queued.status_code == 200
    with Session(engine) as db:
        message = db.get(Message, queued.json()["message_id"])
        assert message.details["context"]["financial_inputs"] == body
        assert message.details["context"]["quote"]["recommended_plan_id"] == "plan_a"
    draft = body | {"monthly_budget_aed": 2000}
    queued_draft = send(client, f"/api/cases/{case}/messages", {
        "text": "What if I can spend more?", "quote_id": quote, "financial_inputs": draft})
    with Session(engine) as db:
        assert db.get(Message, queued_draft.json()["message_id"]).details["context"]["financial_inputs"] == draft
    member = owner[0]
    owner[0] = User(str(uuid4()), "other@example.test")
    assert client.get(f"/api/quotes/{quote}/financial-scenarios").status_code == 404
    owner[0] = member
    assert client.patch("/api/me/profile", json={"expected_version": 2,
                                               "changes": {"annual_budget": 9000}}).status_code == 200
    assert send(client, f"/api/quotes/{quote}/financial-scenarios", body).status_code == 409
