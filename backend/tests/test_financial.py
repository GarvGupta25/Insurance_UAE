from uuid import uuid4

from test_phase_one import facts, send, setup_case

from app.auth import User
from app.domain import compare
from app.financial import financial_scenario


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


def test_scenario_is_saved_by_quote_owner_and_rejects_stale_quote(fixture_client):
    client, owner, _ = fixture_client
    _, quote = setup_case(client)
    body = {"monthly_budget_aed": 1200, "outpatient_spend_aed": 3000,
            "contribution_aed": 1500, "priority": "balanced"}
    key = str(uuid4())
    first = send(client, f"/api/quotes/{quote}/financial-scenarios", body, key)
    assert first.status_code == 200, first.text
    assert send(client, f"/api/quotes/{quote}/financial-scenarios", body, key).json() == first.json()
    saved = client.get(f"/api/quotes/{quote}/financial-scenarios").json()["items"]
    assert len(saved) == 1 and saved[0]["inputs"] == body
    member = owner[0]
    owner[0] = User(str(uuid4()), "other@example.test")
    assert client.get(f"/api/quotes/{quote}/financial-scenarios").status_code == 404
    owner[0] = member
    assert client.patch("/api/me/profile", json={"expected_version": 2,
                                               "changes": {"annual_budget": 9000}}).status_code == 200
    assert send(client, f"/api/quotes/{quote}/financial-scenarios", body).status_code == 409
