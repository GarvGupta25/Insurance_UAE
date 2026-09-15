from app.explanations import recommendation_explanation, servicing_explanation


def test_member_and_broker_explanations_are_independently_safe():
    event = {"outcome": "denied", "reason_code": "benefit_excluded", "calculation": ["This benefit is excluded."]}
    item = {"status": "supported", "reasons": ["The network fits."], "gaps": []}
    for member in [servicing_explanation(event, "member"), recommendation_explanation(item, "member")]:
        assert all(term not in member.lower() for term in ["cohort", "flag", "risk", "reason_code", "reviewer"])
    assert "reason_code" in servicing_explanation(event, "broker")
    assert "flags" in recommendation_explanation(item, "broker")
