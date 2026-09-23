from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import plans
from app.models import ClaimAutoRule, ClaimDecision, ClaimIntake, ClaimQualityAudit, Policy, ProvisionalAuthRule
from conftest import as_assigned_broker


def policy_for(db, owner):
    policy = Policy(owner_id=owner[0].id, status="demo_active",
                    snapshot={"plan": next(plan for plan in plans() if plan["id"] == "plan_a")})
    db.add(policy)
    db.flush()
    return policy


def test_emergency_provisional_letter_and_final_reconciliation(fixture_client):
    client, owner, database = fixture_client
    with Session(database) as db:
        policy = policy_for(db, owner)
        db.add(ProvisionalAuthRule(policy_type="plan_a", claim_category="emergency_room_admission",
                                   max_amount_fils=200000,
                                   requires_conditions=["emergency_flag", "active_policy", "covered_category"],
                                   updated_by="test"))
        db.commit()
        policy_id = policy.id
    submitted = client.post(f"/api/policies/{policy_id}/claim-intakes/free-form",
                            headers={"Idempotency-Key": "emergency-provisional"},
                            json={"message": "I am at the emergency room", "explicit_emergency": True,
                                  "emergency_category": "emergency_room_admission"})
    assert submitted.status_code == 200
    claim_id = submitted.json()["intake_id"]
    assert submitted.json()["provisional_amount_fils"] == 200000
    letter = client.get(f"/api/policies/{policy_id}/claim-intakes/{claim_id}/provisional-letter")
    assert letter.status_code == 200 and letter.content.startswith(b"%PDF")
    with Session(database) as db:
        assert len(db.scalars(select(ClaimDecision).where(ClaimDecision.claim_intake_id == claim_id)).all()) == 1
        assert db.scalars(select(ClaimQualityAudit)).all() == []
    status = client.get(f"/api/policies/{policy_id}/claim-intakes").json()[0]
    assert status["provisional_amount_fils"] == 200000
    assert status["timeline"]["stage"] == "human_review"
    assert any(update["action"] == "provisional_issued" for update in status["updates"])
    with as_assigned_broker(owner, database):
        decision = client.post(f"/api/broker/claims/{claim_id}/review",
                               headers={"Idempotency-Key": "emergency-final-denial"},
                               json={"action": "deny", "note": "Hospital bill still missing."})
        assert decision.status_code == 200
        replay = client.get(f"/api/broker/claims/{claim_id}/replay")
        assert replay.status_code == 200
        assert [row["type"] for row in replay.json()["decisions"]] == ["provisional", "denied"]
        assert any(event["action"] == "provisional_reconciled" for event in replay.json()["events"])
    status = client.get(f"/api/policies/{policy_id}/claim-intakes").json()[0]
    assert status["decision"]["outcome"] == "denied"
    assert status["net_due_fils"] == 0


def test_unlisted_emergency_never_gets_provisional(fixture_client):
    client, owner, database = fixture_client
    with Session(database) as db:
        policy = policy_for(db, owner)
        db.commit()
        policy_id = policy.id
    response = client.post(f"/api/policies/{policy_id}/claim-intakes/free-form",
                           headers={"Idempotency-Key": "unknown-emergency"},
                           json={"message": "An accident happened", "explicit_emergency": True,
                                 "emergency_category": "other"})
    assert response.status_code == 200
    assert response.json()["provisional_amount_fils"] is None
    with Session(database) as db:
        assert db.scalars(select(ClaimDecision)).all() == []


def test_auto_cap_raise_requires_reviewed_samples(fixture_client):
    client, owner, database = fixture_client
    with Session(database) as db:
        policy_for(db, owner)
        db.commit()
    with as_assigned_broker(owner, database):
        response = client.post("/api/broker/claims/rules/automatic",
                               headers={"Idempotency-Key": "unsafe-cap-raise"},
                               json={"policy_type": "plan_a", "claim_category": "general",
                                     "max_amount_aed": 20000})
        assert response.status_code == 409
        safe = client.post("/api/broker/claims/rules/automatic",
                           headers={"Idempotency-Key": "safe-cap"},
                           json={"policy_type": "plan_a", "claim_category": "general",
                                 "max_amount_aed": 500})
        assert safe.status_code == 200
    with Session(database) as db:
        rule = db.scalar(select(ClaimAutoRule))
        assert rule.max_amount_fils == 50000


def test_denied_claim_appeal_is_prepared_for_human_only(fixture_client):
    client, owner, database = fixture_client
    with Session(database) as db:
        policy = policy_for(db, owner)
        db.commit()
        policy_id = policy.id
    started = client.post(f"/api/policies/{policy_id}/claim-intakes/structured",
                          headers={"Idempotency-Key": "appeal-source"},
                          json={"kind": "claim", "event_id": "APPEAL-SOURCE", "policy_month": 1,
                                "benefit_class": "general", "provider_tier": "in_network_clinic",
                                "billed_amount": 750, "documents": []}).json()
    claim_id = started["intake_id"]
    with as_assigned_broker(owner, database):
        assert client.post(f"/api/broker/claims/{claim_id}/review",
                           headers={"Idempotency-Key": "appeal-denial"},
                           json={"action": "deny", "note": "Bill missing."}).status_code == 200
    draft = client.post(f"/api/policies/{policy_id}/claim-intakes/{claim_id}/appeal-draft",
                        json={"evidence": ["A new hospital invoice is available"]})
    assert draft.status_code == 200
    assert draft.json()["decision_authority"] == "human_broker_only"
    appeal = client.post(f"/api/policies/{policy_id}/claim-intakes/{claim_id}/appeal",
                         headers={"Idempotency-Key": "appeal-submit"},
                         json={"statement": "Please reconsider my hospital bill.",
                               "evidence": ["A new hospital invoice is available"]})
    assert appeal.status_code == 200
    assert appeal.json()["route"] == "human_review"
    appeal_id = appeal.json()["appeal_id"]
    with Session(database) as db:
        assert db.get(ClaimIntake, appeal_id).kind == "appeal"
        assert db.scalar(select(ClaimDecision).where(ClaimDecision.claim_intake_id == appeal_id)) is None
    with as_assigned_broker(owner, database):
        queue = client.get("/api/broker/claims").json()
        assert any(row["id"] == appeal_id for row in queue)
        assert client.post(f"/api/broker/claims/{appeal_id}/appeal-review",
                           headers={"Idempotency-Key": "appeal-review-human"},
                           json={"action": "uphold", "note": "Evidence does not resolve the missing bill."}).status_code == 200
    status = client.get(f"/api/policies/{policy_id}/claim-intakes").json()
    assert next(row for row in status if row["id"] == appeal_id)["timeline"]["stage"] == "appeal_reviewed"


def test_quality_sample_reviewer_and_observability(fixture_client):
    client, owner, database = fixture_client
    with Session(database) as db:
        policy = policy_for(db, owner)
        intake = ClaimIntake(policy_id=policy.id, kind="claim", structured_fields={"event_id": "AUDIT-1"})
        db.add(intake)
        db.flush()
        sample = ClaimQualityAudit(claim_intake_id=intake.id)
        db.add(sample)
        db.commit()
        sample_id = sample.id
    with as_assigned_broker(owner, database):
        samples = client.get("/api/broker/claims/quality-samples")
        assert samples.status_code == 200 and samples.json()[0]["id"] == sample_id
        reviewed = client.post(f"/api/broker/claims/quality-samples/{sample_id}/review",
                               headers={"Idempotency-Key": "quality-sample-reviewed"},
                               json={"status": "incorrect", "note": "The cited document did not support this approval."})
        assert reviewed.status_code == 200
        metrics = client.get("/api/broker/claims/observability")
        assert metrics.status_code == 200
        assert metrics.json()["false_auto_rate_pct"] == 100.0
        assert metrics.json()["reviewed_samples"] == 1
