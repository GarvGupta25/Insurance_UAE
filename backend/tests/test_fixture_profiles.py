from app.contracts import Facts
from app.domain import fixture_facts, source_data


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
