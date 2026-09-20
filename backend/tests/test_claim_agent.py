import ast
import json
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import claim_agent
from app.models import ClaimDocument, ClaimIntake, Policy


def policy(db: Session, owner_id: str) -> str:
    row = Policy(owner_id=owner_id, status="demo_active", snapshot={"plan": {"id": "demo"}})
    db.add(row)
    db.commit()
    return row.id


def complete_bill() -> dict:
    return {
        "doc_type": "bill",
        "metadata": {
            "provider_name": "Crescent Clinic",
            "service_date": "2026-09-20",
            "amount": 750,
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
    }
    assert result["missing_fields"] == ["provider_tier"]
    assert result["follow_up"] == "Is the provider in network, private, or out of network?"


def test_claim_agent_has_no_servicing_dependency():
    source = open(claim_agent.__file__, encoding="utf-8").read()
    imports = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    ]
    assert "servicing" not in imports
    assert not any(name in source for name in ("record_financial_event", "evaluate_servicing"))


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
