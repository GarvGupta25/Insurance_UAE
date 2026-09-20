import ast
import json
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import claim_agent
from app.domain import plans
from app.models import ClaimDocument, ClaimFlag, ClaimIntake, Policy, ServicingEvent


def policy(db: Session, owner_id: str) -> str:
    row = Policy(
        owner_id=owner_id,
        status="demo_active",
        snapshot={"plan": next(plan for plan in plans() if plan["id"] == "plan_a")},
    )
    db.add(row)
    db.commit()
    return row.id


def complete_bill(amount: int = 750) -> dict:
    return {
        "doc_type": "bill",
        "metadata": {
            "provider_name": "Crescent Clinic",
            "service_date": "2026-09-20",
            "amount": amount,
        },
    }


def test_complete_structured_intake_persists_validated_document(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy_id = policy(db, owner[0].id)

    response = client.post(
        f"/api/policies/{policy_id}/claim-intakes/structured",
        headers={"Idempotency-Key": "structured-1"},
        json={
            "kind": "claim",
            "event_id": "CLM-101",
            "policy_month": 4,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "billed_amount": 750,
            "documents": [complete_bill()],
        },
    )

    assert response.status_code == 200
    assert response.json()["completeness_ok"] is True
    with Session(engine) as db:
        intake = db.get(ClaimIntake, response.json()["intake_id"])
        document = db.scalar(select(ClaimDocument).where(ClaimDocument.claim_intake_id == intake.id))
        assert intake.kind == "claim"
        assert intake.structured_fields["billed_amount"] == 750
        assert document.completeness_ok is True


def test_missing_required_document_is_explained(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy_id = policy(db, owner[0].id)

    response = client.post(
        f"/api/policies/{policy_id}/claim-intakes/structured",
        headers={"Idempotency-Key": "structured-2"},
        json={
            "kind": "reimbursement",
            "event_id": "RMB-101",
            "policy_month": 2,
            "benefit_class": "general",
            "provider_tier": "out_of_network",
            "amount_paid_by_member": 400,
        },
    )

    assert response.status_code == 200
    assert response.json()["completeness_ok"] is False
    assert response.json()["missing"] == ["Upload a complete bill."]
    assert response.json()["message"] == "Upload a complete bill."
    assert response.json()["route"] == "review"
    with Session(engine) as db:
        flag = db.scalar(select(ClaimFlag).where(ClaimFlag.claim_intake_id == response.json()["intake_id"]))
        assert flag.flag_type == "missing_docs"


def test_free_form_uses_one_call_and_asks_about_only_ambiguous_field(monkeypatch, fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy_id = policy(db, owner[0].id)

    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            extracted = {
                "kind": "claim",
                "provider_name": "Crescent Clinic",
                "provider_tier": None,
                "benefit_class": "general",
                "amount": 750,
            }
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(extracted)))]
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

    response = client.post(
        f"/api/policies/{policy_id}/claim-intakes/free-form",
        headers={"Idempotency-Key": "free-form-1"},
        json={
            "message": "I received a general-care bill for AED 750 from Crescent Clinic.",
            "documents": [complete_bill()],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert len(calls) == 1
    assert result["structured_fields"] == {
        "provider_name": "Crescent Clinic",
        "provider_tier": None,
        "benefit_class": "general",
        "billed_amount": 750,
        "follow_up": "Is the provider in network, private, or out of network?",
    }
    assert result["missing_fields"] == ["provider_tier"]
    assert result["follow_up"] == "Is the provider in network, private, or out of network?"


def test_claim_agent_uses_the_existing_servicing_writer_without_calculating_decisions():
    source = open(claim_agent.__file__, encoding="utf-8").read()
    imports = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert "servicing" in imports
    assert "record_financial_event" in source
    assert "evaluate_servicing" not in source


def test_structured_intake_accepts_existing_ui_preauth_name():
    body = claim_agent.StructuredClaimIntake(
        kind="preauth",
        event_id="PRE-101",
        policy_month=1,
        benefit_class="general",
        provider_tier="in_network_clinic",
        estimated_amount=500,
    )

    assert body.kind == "pre_auth"


def test_clean_low_value_claim_runs_straight_through_the_servicing_event_log(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy_id = policy(db, owner[0].id)

    response = client.post(
        f"/api/policies/{policy_id}/claim-intakes/structured",
        headers={"Idempotency-Key": "straight-through-1"},
        json={
            "kind": "claim",
            "event_id": "CLM-STP-1",
            "policy_month": 4,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "billed_amount": 750,
            "documents": [complete_bill()],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["route"] == "straight_through"
    assert result["decision"]["outcome"] == "covered"
    assert "Your request was covered." in result["member_explanation"]
    with Session(engine) as db:
        intake = db.get(ClaimIntake, result["intake_id"])
        event = db.scalar(select(ServicingEvent).where(ServicingEvent.id == result["decision"]["id"]))
        assert intake.structured_fields["servicing_event_id"] == event.id
        assert db.scalars(select(ClaimFlag).where(ClaimFlag.claim_intake_id == intake.id)).all() == []


def test_high_value_and_insufficient_data_claims_are_flagged_for_review(fixture_client):
    client, owner, engine = fixture_client
    with Session(engine) as db:
        policy_id = policy(db, owner[0].id)
        annual_limit = db.get(Policy, policy_id).snapshot["plan"]["annual_limit"]

    high_value = client.post(
        f"/api/policies/{policy_id}/claim-intakes/structured",
        headers={"Idempotency-Key": "high-value-1"},
        json={
            "kind": "claim",
            "event_id": "CLM-HIGH-1",
            "policy_month": 4,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "billed_amount": annual_limit // 10,
            "documents": [complete_bill(annual_limit // 10)],
        },
    )
    insufficient = client.post(
        f"/api/policies/{policy_id}/claim-intakes/structured",
        headers={"Idempotency-Key": "insufficient-1"},
        json={
            "kind": "claim",
            "event_id": "CLM-UNKNOWN-1",
            "policy_month": 4,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "geography": "abroad",
            "billed_amount": 750,
            "documents": [complete_bill()],
        },
    )

    assert high_value.json()["route"] == "review"
    assert insufficient.json()["route"] == "review"
    assert insufficient.json()["decision"]["outcome"] == "insufficient_data"
    with Session(engine) as db:
        flags = db.scalars(select(ClaimFlag).order_by(ClaimFlag.created_at)).all()
        assert [(flag.flag_type, flag.reason) for flag in flags] == [
            ("high_value", f"AED {annual_limit // 10} meets or exceeds the AED {annual_limit // 10}.00 review threshold (10% of the annual limit)."),
            ("exclusion_risk", "The deterministic servicing engine returned insufficient_data and requires human review."),
        ]


def test_an_open_flag_blocks_straight_through_processing(fixture_client):
    _, owner, engine = fixture_client
    with Session(engine) as db:
        policy_id = policy(db, owner[0].id)
        intake = ClaimIntake(
            policy_id=policy_id,
            kind="claim",
            structured_fields={
                "event_id": "CLM-FLAGGED-1",
                "policy_month": 4,
                "benefit_class": "general",
                "provider_tier": "in_network_clinic",
                "billed_amount": 750,
            },
        )
        db.add(intake)
        db.flush()
        db.add_all(
            (
                ClaimDocument(
                    claim_intake_id=intake.id,
                    doc_type="bill",
                    extracted_fields=complete_bill()["metadata"],
                    completeness_ok=True,
                ),
                ClaimFlag(claim_intake_id=intake.id, flag_type="anomaly", reason="Repeated bill metadata."),
            )
        )
        db.commit()

        result = claim_agent.route_claim_intake(db, db.get(Policy, policy_id), intake.id, {"intake_id": intake.id})

        assert result["route"] == "review"
        assert db.scalars(select(ServicingEvent).where(ServicingEvent.policy_id == policy_id)).all() == []
