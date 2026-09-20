from types import SimpleNamespace

from conftest import as_assigned_broker
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import claim_agent
from app.domain import plans
from app.models import ClaimFlag, ClaimIntake, Policy, ServicingEvent


def add_policy(db: Session, owner_id: str) -> Policy:
    policy = Policy(
        owner_id=owner_id,
        status="demo_active",
        snapshot={"plan": next(plan for plan in plans() if plan["id"] == "plan_a")},
    )
    db.add(policy)
    db.commit()
    return policy


def bill(amount: int = 750) -> dict:
    return {
        "doc_type": "bill",
        "metadata": {
            "provider_name": "Crescent Clinic",
            "service_date": "2026-09-20",
            "amount": amount,
        },
    }


def claim_body(reference: str, amount: int = 750) -> dict:
    return {
        "kind": "claim",
        "event_id": reference,
        "policy_month": 4,
        "benefit_class": "general",
        "provider_name": "Crescent Clinic",
        "provider_tier": "in_network_clinic",
        "billed_amount": amount,
        "documents": [bill(amount)],
    }


def test_emergency_fast_path_is_fixed_immediate_pinned_and_inert(monkeypatch, fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        policy_id = policy.id

    monkeypatch.setattr(
        claim_agent,
        "settings",
        lambda: SimpleNamespace(
            send_real_emergency_alert=False, groq_api_key="", groq_model="test-model"
        ),
    )
    first = client.post(
        f"/api/policies/{policy_id}/claim-intakes/free-form",
        headers={"Idempotency-Key": "emergency-1"},
        json={"message": "I'm at Rashid Hospital with chest pain and they want to admit me."},
    )
    explicit = client.post(
        f"/api/policies/{policy_id}/claim-intakes/free-form",
        headers={"Idempotency-Key": "emergency-2"},
        json={"message": "I need urgent help.", "explicit_emergency": True},
    )

    assert first.status_code == explicit.status_code == 200
    assert first.json()["message"] == explicit.json()["message"] == claim_agent.EMERGENCY_GUIDANCE
    assert first.json()["alert_sent"] is explicit.json()["alert_sent"] is False
    with Session(engine) as db:
        intake = db.get(ClaimIntake, first.json()["intake_id"])
        flag = db.scalar(select(ClaimFlag).where(ClaimFlag.claim_intake_id == intake.id))
        assert intake.kind == "emergency" and intake.is_emergency is True
        assert flag.flag_type == "emergency" and flag.status == "open"

    with as_assigned_broker(owner, engine):
        queue = client.get("/api/broker/claims").json()
    assert queue[0]["id"] == first.json()["intake_id"]
    assert queue[0]["transcript"][1]["content"] == claim_agent.EMERGENCY_GUIDANCE


def test_emergency_uses_same_intake_when_documents_arrive(monkeypatch, fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        policy_id = policy.id
    monkeypatch.setattr(
        claim_agent,
        "settings",
        lambda: SimpleNamespace(
            send_real_emergency_alert=False, groq_api_key="", groq_model="test-model"
        ),
    )
    emergency = client.post(
        f"/api/policies/{policy_id}/claim-intakes/free-form",
        headers={"Idempotency-Key": "emergency-complete-1"},
        json={"message": "Ambulance brought me to the emergency room."},
    ).json()
    completed = client.post(
        f"/api/policies/{policy_id}/claim-intakes/{emergency['intake_id']}/complete",
        headers={"Idempotency-Key": "emergency-complete-2"},
        json=claim_body("CLM-EMERGENCY-COMPLETE"),
    )

    assert completed.status_code == 200
    assert completed.json()["intake_id"] == emergency["intake_id"]
    assert completed.json()["route"] == "straight_through"
    with Session(engine) as db:
        intake = db.get(ClaimIntake, emergency["intake_id"])
        flag = db.scalar(
            select(ClaimFlag).where(
                ClaimFlag.claim_intake_id == intake.id,
                ClaimFlag.flag_type == "emergency",
            )
        )
        assert intake.kind == "claim" and intake.is_emergency is True
        assert flag.status == "reviewed"


def test_appeal_draft_uses_real_reason_and_only_member_evidence(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        policy_id = policy.id
        event = ServicingEvent(
            owner_id=owner[0].id,
            policy_id=policy.id,
            root_id="CLM-DENIED-1",
            record_type="decision",
            kind="claim",
            effective_month=1,
            sequence=1,
            payload={},
            outcome="denied",
            reason_code="provider_out_of_network",
            plan_pays_fils=0,
            member_pays_fils=75000,
            calculation=["Provider was outside the saved network."],
        )
        db.add(event)
        db.commit()

    response = client.post(
        f"/api/policies/{policy_id}/claim-intakes/appeal-draft",
        json={
            "contested_event_id": "CLM-DENIED-1",
            "new_evidence": ["Hospital network confirmation dated 20 September 2026"],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert "provider_out_of_network" in result["statement"]
    assert "Hospital network confirmation dated 20 September 2026" in result["statement"]
    assert "doctor letter" not in result["statement"].lower()


def test_explainable_anomaly_timeline_and_real_stp_metric(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy = add_policy(db, owner[0].id)
        policy_id = policy.id
    first = client.post(
        f"/api/policies/{policy_id}/claim-intakes/structured",
        headers={"Idempotency-Key": "metric-1"},
        json=claim_body("CLM-METRIC-1"),
    )
    second = client.post(
        f"/api/policies/{policy_id}/claim-intakes/structured",
        headers={"Idempotency-Key": "metric-2"},
        json=claim_body("CLM-METRIC-2"),
    )

    assert first.json()["route"] == "straight_through"
    assert second.json()["route"] == "review"
    with Session(engine) as db:
        anomaly = db.scalar(
            select(ClaimFlag).where(
                ClaimFlag.claim_intake_id == second.json()["intake_id"],
                ClaimFlag.flag_type == "anomaly",
            )
        )
        assert anomaly.reason == (
            "A claim with the same provider, benefit class, and amount was submitted within 7 days."
        )

    timeline = client.get(f"/api/policies/{policy_id}/claim-intakes")
    assert timeline.status_code == 200
    assert timeline.json()[0]["timeline"]["stage"] == "human_review"
    assert timeline.json()[1]["timeline"]["stage"] == "decision_recorded"
    assert timeline.json()[1]["decision"]["calculation"]
    assert "never sets approval" in timeline.json()[1]["why_not_black_box"]

    with as_assigned_broker(owner, engine):
        analytics = client.get("/api/broker/claims/analytics")
    assert analytics.status_code == 200
    assert analytics.json() == {
        "total_intakes": 2,
        "straight_through": 1,
        "straight_through_rate_pct": 50.0,
        "definition": "Decisive servicing decisions completed without any claim flag or human review.",
    }
