from uuid import uuid4

from conftest import as_assigned_broker

from app.auth import User
from app.contracts import Facts, challenge_readiness, readiness
from app.domain import classify, compare, fixture_facts, source_data


def fixture_application_facts(profile):
    """Add synthetic UAE application fields without changing supplied judging facts."""
    return {
        **fixture_facts(profile),
        "legal_name": profile["label"],
        "date_of_birth": "1994-03-12",
        "nationality": "Indian",
        "residency": "resident",
        "emirate": "Dubai",
        "emirates_id_status": "issued",
        "diagnosed_conditions": "yes" if profile["conditions"] else "no",
        "smoker": "yes" if profile["smoker"] else "no",
        "maternity": False,
        "geography": "UAE",
        "start_date": "2026-10-01",
        "payer": "self",
        "annual_budget": 25000,
        "strict_budget": False,
        "payment_frequency": "annual",
        "immediate_chronic_cover": False if profile["conditions"] else None,
    }


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


def test_applicant_65_or_older_requires_medical_disclosure_before_standard_quote():
    items = compare({"age": 66})
    assert len(items) == 3
    assert all(item["status"] == "needs_more_information" for item in items)
    assert all("additional medical disclosure required" in item["unknowns"][0].lower() for item in items)


def test_fixture_adapter_does_not_mutate_the_source_profile():
    profile = source_data()["profiles"][2]
    facts = fixture_facts(profile)
    facts["conditions"].append("extra")
    facts["priorities"].clear()
    assert profile["conditions"] == ["type 2 diabetes (managed)", "hypertension (managed)"]
    assert profile["stated_priorities"] == ["ongoing coverage for existing conditions", "cost matters"]


def test_compact_judging_fixture_has_an_explicit_readiness_adapter():
    short = {
        "age": 32, "marital_status": "married", "smoker": "no",
        "diagnosed_conditions": "no", "budget_category": "moderate",
        "priorities": ["hospital access"],
    }
    assert challenge_readiness(short)["ready"]
    expanded = {**short, "legal_name": "Demo Member", "payer": "self"}
    assert challenge_readiness(expanded)["mode"] == "challenge"
    assert challenge_readiness(expanded)["ready"]


def test_user_facing_readiness_requires_the_uae_application_profile():
    result = readiness({})
    assert result["mode"] == "extended"
    assert result["missing"][:6] == [
        "legal_name", "date_of_birth", "nationality", "residency", "emirate", "emirates_id_status"
    ]
    assert "near_term_needs" in result["missing"]


def test_diagnosis_answer_can_be_saved_before_condition_name():
    partial = Facts.model_validate({"diagnosed_conditions": "yes"}).model_dump()
    assert "conditions" in readiness(partial)["missing"]


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


def test_original_applicants_can_get_real_quotations_with_the_uae_application_profile(fixture_client):
    client, owner, engine = fixture_client
    expected = {"P1": "plan_a", "P2": "plan_c", "P3": "plan_b", "P4": "plan_b", "P5": "plan_c"}
    for profile in source_data()["profiles"]:
        owner[0] = User(str(uuid4()), f"{profile['id'].lower()}@example.test")
        facts = fixture_application_facts(profile)
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
        if profile["id"] == "P3":
            prepared = client.post(
                "/api/applications/prepare",
                json={"quote_id": quote.json()["id"], "plan_id": "plan_b", "request_broker_review": True},
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert prepared.status_code == 200, prepared.text
            with as_assigned_broker(owner, engine):
                broker_queue = client.get("/api/broker/recommendations").json()
            assert broker_queue[0]["certainty"] == "tradeoff"
            assert "6-month waiting period" in broker_queue[0]["summary"]["decision_brief"]["main_uncertainty"]
