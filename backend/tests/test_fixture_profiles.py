from uuid import uuid4

from app.auth import User
from app.contracts import Facts, readiness
from app.domain import classify, compare, fixture_facts, source_data


def test_original_applicants_fit_the_typed_profile_without_leaking_future_outcomes():
    profiles = source_data()["profiles"]
    assert [profile["id"] for profile in profiles] == ["P1", "P2", "P3", "P4", "P5"]

    for profile in profiles:
        facts = fixture_facts(profile)
        assert Facts.model_validate(facts).model_dump(exclude_unset=True) == facts
        assert facts["age"] == profile["age"]
        assert facts["conditions"] == profile["conditions"]
        assert facts["near_term_needs"] == profile["near_term_needs"]
        assert "approved_plan_id" not in facts
        assert "policy_inception" not in facts


def test_fixture_adapter_does_not_mutate_the_source_profile():
    profile = source_data()["profiles"][2]
    facts = fixture_facts(profile)
    facts["conditions"].append("extra")
    facts["priorities"].clear()
    assert profile["conditions"] == ["type 2 diabetes (managed)", "hypertension (managed)"]
    assert profile["stated_priorities"] == ["ongoing coverage for existing conditions", "cost matters"]


def test_original_applicants_have_expected_deterministic_routing_and_recommendations():
    expected = {
        "P1": ("general_needs", "under_40", "plan_a"),
        "P2": ("near_term_maternity", "under_40", "plan_c"),
        "P3": ("ongoing_chronic_care", "55_plus", "plan_b"),
        "P4": ("general_needs", "40_54", "plan_b"),
        "P5": ("complex_ongoing_care", "55_plus", "plan_c"),
    }
    for profile in source_data()["profiles"]:
        facts = fixture_facts(profile)
        routing = classify(facts)
        comparison = compare(facts)
        assert (routing["cohort"], routing["age_band"], comparison[0]["plan"]["id"]) == expected[profile["id"]]
        assert len(comparison) == 3
        assert all(item["plan"]["annual_premium"] in {4200, 8900, 16500} for item in comparison)

    p3_facts = fixture_facts(source_data()["profiles"][2])
    p3_balanced = next(item for item in compare(p3_facts) if item["plan"]["id"] == "plan_b")
    assert p3_balanced["status"] == "supported"
    assert "6-month waiting period" in p3_balanced["tradeoffs"][0]


def test_original_applicants_can_get_real_quotations_without_identity_or_payment_details(fixture_client):
    client, owner, _ = fixture_client
    expected = {"P1": "plan_a", "P2": "plan_c", "P3": "plan_b", "P4": "plan_b", "P5": "plan_c"}
    for profile in source_data()["profiles"]:
        owner[0] = User(str(uuid4()), f"{profile['id'].lower()}@example.test")
        facts = fixture_facts(profile)
        assert readiness(facts)["ready"]
        current = client.get("/api/me/profile").json()
        saved = client.patch("/api/me/profile", json={"expected_version": current["version"], "changes": facts})
        assert saved.status_code == 200, saved.text
        case = client.post("/api/cases", json={}, headers={"Idempotency-Key": str(uuid4())}).json()["id"]
        quote = client.post(f"/api/cases/{case}/quotes", json={}, headers={"Idempotency-Key": str(uuid4())})
        assert quote.status_code == 200, quote.text
        snapshot = client.get(f"/api/quotes/{quote.json()['id']}").json()
        assert snapshot["recommended_plan_id"] == expected[profile["id"]]
        assert snapshot["classification"]["cohort"] == classify(facts)["cohort"]
        assert len(snapshot["items"]) == 3
