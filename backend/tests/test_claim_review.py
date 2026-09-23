import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from conftest import as_assigned_broker
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import claim_agent
from app.domain import plans
from app.models import (
    Audit,
    ClaimDocument,
    ClaimFlag,
    ClaimIntake,
    Policy,
    ReviewDecision,
    ServicingEvent,
)


def add_policy(db: Session, owner_id: str) -> Policy:
    policy = Policy(
        owner_id=owner_id,
        status="demo_active",
        snapshot={"plan": next(plan for plan in plans() if plan["id"] == "plan_a")},
    )
    db.add(policy)
    db.flush()
    return policy


def add_flagged_claim(
    db: Session,
    policy: Policy,
    reference: str,
    *,
    emergency: bool = False,
    created_at: datetime | None = None,
) -> ClaimIntake:
    amount = policy.snapshot["plan"]["annual_limit"] // 10
    intake = ClaimIntake(
        policy_id=policy.id,
        kind="claim",
        raw_message=f"Please review {reference}.",
        structured_fields={
            "event_id": reference,
            "policy_month": 4,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "billed_amount": amount,
            "follow_up": "I have captured the claim details for broker review.",
        },
        # Phase 4 pinning is driven by the open emergency flag, even before Phase 5
        # starts setting the convenience field on new emergency intakes.
        is_emergency=False,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(intake)
    db.flush()
    db.add(
        ClaimDocument(
            claim_intake_id=intake.id,
            doc_type="bill",
            extracted_fields={
                "provider_name": "Crescent Clinic",
                "service_date": "2026-09-20",
                "amount": amount,
            },
            completeness_ok=True,
        )
    )
    db.add(
        ClaimFlag(
            claim_intake_id=intake.id,
            flag_type="emergency" if emergency else "high_value",
            reason="Emergency review required." if emergency else "High-value review required.",
        )
    )
    db.flush()
    return intake


def test_emergency_claims_are_first_with_read_only_broker_suggestions(monkeypatch, fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        ordinary = add_flagged_claim(db, policy, "CLM-ORDINARY", created_at=datetime.now(timezone.utc))
        emergency = add_flagged_claim(
            db,
            policy,
            "CLM-EMERGENCY",
            emergency=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=365),
        )
        db.commit()
        ordinary_id = ordinary.id
        emergency_id = emergency.id

    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                    "action": "escalate_to_senior_broker",
                    "reasoning": "The open flag requires broker review.",
                })))]
            )

    monkeypatch.setattr(
        claim_agent,
        "settings",
        lambda: SimpleNamespace(groq_api_key="test", groq_model="test-model"),
    )
    monkeypatch.setattr(
        claim_agent,
        "Groq",
        lambda **_: SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )

    with as_assigned_broker(owner, engine):
        response = client.get("/api/broker/claims")

    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [emergency_id, ordinary_id]
    assert calls == []
    assert rows[0]["suggested_action"]["source"] == "rule_fallback"
    assert rows[0]["transcript"] == [
        {"role": "member", "content": "Please review CLM-EMERGENCY."},
        {"role": "claim_agent", "content": "I have captured the claim details for broker review."},
    ]
    assert rows[0]["documents"][0]["extracted_fields"]["provider_name"] == "Crescent Clinic"


def test_approve_calls_real_servicing_and_attributes_the_append_only_review(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        intake = add_flagged_claim(db, policy, "CLM-APPROVE")
        db.commit()
        intake_id = intake.id

    with as_assigned_broker(owner, engine) as broker:
        response = client.post(
            f"/api/broker/claims/{intake_id}/review",
            headers={"Idempotency-Key": "claim-approve"},
            json={"action": "approve", "note": "Verified documents and confirmed deterministic handling."},
        )

    assert response.status_code == 200
    result = response.json()
    assert result["decision"]["event_id"] == "CLM-APPROVE"
    assert result["review"]["decided_by"] == "reviewer"
    with Session(engine) as db:
        event = db.get(ServicingEvent, result["review"]["servicing_event_id"])
        reviews = db.scalars(select(ReviewDecision).where(ReviewDecision.owner_id == broker.id)).all()
        audits = db.scalars(select(Audit).where(Audit.owner_id == broker.id, Audit.action == "claim_reviewed")).all()
        assert event is not None
        assert event.outcome == result["decision"]["outcome"]
        assert len(reviews) == 1
        assert reviews[0].after["decided_by"] == "reviewer"
        assert reviews[0].servicing_event_id == event.id
        assert audits[0].details["decided_by"] == "reviewer"


def test_each_claim_action_appends_a_new_attributed_record(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        intake = add_flagged_claim(db, policy, "CLM-MORE-INFO")
        db.commit()
        intake_id = intake.id

    with as_assigned_broker(owner, engine) as broker:
        first = client.post(
            f"/api/broker/claims/{intake_id}/review",
            headers={"Idempotency-Key": "claim-more-info-1"},
            json={"action": "request_more_information", "note": "Please verify the treating provider."},
        )
        second = client.post(
            f"/api/broker/claims/{intake_id}/review",
            headers={"Idempotency-Key": "claim-more-info-2"},
            json={"action": "escalate_to_senior_broker", "note": "Escalating after the follow-up review."},
        )

    assert first.status_code == second.status_code == 200
    with Session(engine) as db:
        reviews = db.scalars(
            select(ReviewDecision)
            .where(ReviewDecision.owner_id == broker.id)
            .order_by(ReviewDecision.created_at, ReviewDecision.id)
        ).all()
        assert len(reviews) == 2
        assert len({review.id for review in reviews}) == 2
        assert [review.action for review in reviews] == [
            "request_more_information",
            "escalate_to_senior_broker",
        ]
        assert all(review.after["decided_by"] == "reviewer" for review in reviews)
