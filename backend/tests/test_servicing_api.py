from datetime import date, timedelta
from uuid import uuid4

from conftest import as_assigned_broker
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import source_data
from app.models import Message, ServicingEvent


def post(client, path, body):
    return client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})


def broker_post(fixture_client, path, body):
    client, owner, engine = fixture_client
    with as_assigned_broker(owner, engine):
        return post(client, path, body)


def broker_get(fixture_client, path):
    client, owner, engine = fixture_client
    with as_assigned_broker(owner, engine):
        return client.get(path)


def create_policy(fixture_client, plan_id="plan_a"):
    client, _, _ = fixture_client
    profile = client.get("/api/me/profile").json()
    facts = {
        "legal_name": "Amina Example",
        "date_of_birth": "1994-03-12",
        "nationality": "Indian",
        "residency": "resident",
        "emirate": "Dubai",
        "diagnosed_conditions": "no",
        "conditions": [],
        "smoker": "no",
        "maternity": False,
        "geography": "UAE",
        "start_date": (date.today() + timedelta(days=1)).isoformat(),
        "payer": "self",
        "annual_budget": 12000,
        "strict_budget": False,
        "payment_frequency": "annual",
    }
    assert client.patch("/api/me/profile", json={"expected_version": profile["version"], "changes": facts}).status_code == 200
    case = post(client, "/api/cases", {}).json()["id"]
    quote = post(client, f"/api/cases/{case}/quotes", {}).json()["id"]
    application = post(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": plan_id, "request_broker_review": True}).json()["id"]
    preview = client.get(f"/api/applications/{application}").json()
    assert broker_post(
        fixture_client,
        f"/api/broker/recommendations/{preview['recommendation_id']}/review",
        {"action": "approve", "note": "Synthetic broker review."},
    ).status_code == 200
    preview = client.get(f"/api/applications/{application}").json()
    return post(client, f"/api/applications/{application}/submit", {"payload_hash": preview["payload_hash"], "declarations_confirmed": True}).json()["policy_id"]


def test_servicing_endpoint_persists_claim_and_keeps_forecast_out_of_ledger(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(fixture_client)
    preauth = post(
        client,
        f"/api/policies/{policy}/servicing",
        {"event_id": "PRE-X", "kind": "preauth", "policy_month": 3, "benefit_class": "general", "provider_tier": "in_network_clinic", "estimated_amount": 3000},
    )
    assert preauth.status_code == 200
    assert preauth.json()["ledger"]["annual_paid_fils"] == 0
    claim = post(
        client,
        f"/api/policies/{policy}/servicing",
        {"event_id": "CLM-X", "kind": "claim", "policy_month": 3, "benefit_class": "general", "provider_tier": "in_network_clinic", "billed_amount": 3000},
    )
    assert claim.status_code == 200
    assert claim.json()["decision"]["outcome"] == "covered"
    detail = client.get(f"/api/policies/{policy}").json()
    assert [item["event_id"] for item in detail["servicing"]] == ["PRE-X", "CLM-X"]
    assert detail["servicing"][0]["ledger_after"]["annual_paid_fils"] == 0


def test_policy_agent_receives_recorded_receipts_and_claim_ledger(fixture_client):
    client, _, engine = fixture_client
    policy = create_policy(fixture_client)
    detail = client.get(f"/api/policies/{policy}").json()
    order = post(client, f"/api/instalments/{detail['instalments'][0]['id']}/payment-order", {}).json()
    assert post(client, f"/api/payment-orders/{order['id']}/simulate", {"result": "captured"}).status_code == 200
    claim = post(client, f"/api/policies/{policy}/servicing", {
        "event_id": "AGENT-CLM", "kind": "claim", "policy_month": 0,
        "benefit_class": "general", "provider_tier": "in_network_clinic", "billed_amount": 500,
    })
    assert claim.status_code == 200
    case = client.get("/api/cases").json()[0]["id"]
    sent = post(client, f"/api/cases/{case}/messages", {
        "text": "What has been paid and how much deductible have I met?", "policy_id": policy,
    })
    assert sent.status_code == 200
    with Session(engine) as db:
        context = db.scalar(select(Message).where(Message.id == sent.json()["message_id"])).details["context"]
    assert context["payments"]["receipt_total_fils"] == detail["total_fils"]
    assert context["payments"]["receipt_total_aed"] == 4200
    assert context["servicing_ledger"]["deductible_met_fils"] == 50000
    assert context["servicing_ledger_aed"]["deductible_met"] == 500
    assert context["recent_servicing"][0]["event_id"] == "AGENT-CLM"


def test_servicing_preview_is_read_only_and_rejects_a_stale_confirmation(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(fixture_client)
    body = {"event_id": "PREVIEW-X", "kind": "claim", "policy_month": 3, "benefit_class": "general", "provider_tier": "in_network_clinic", "billed_amount": 3000}
    preview = client.post(f"/api/policies/{policy}/servicing/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["decision"]["plan_pays"] == 1050
    assert client.get(f"/api/policies/{policy}").json()["servicing"] == []

    other = post(client, f"/api/policies/{policy}/servicing", {**body, "event_id": "OTHER-X"})
    assert other.status_code == 200, other.text
    stale = post(client, f"/api/policies/{policy}/servicing", {**body, "expected_policy_version": preview.json()["policy_version"]})
    assert stale.status_code == 409
    fresh = client.post(f"/api/policies/{policy}/servicing/preview", json=body).json()
    submitted = post(client, f"/api/policies/{policy}/servicing", {**body, "expected_policy_version": fresh["policy_version"]})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["decision"]["plan_pays_fils"] == fresh["decision"]["plan_pays_fils"]


def test_late_earlier_claim_appends_revised_effective_decisions(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(fixture_client, "plan_b")
    body = {"kind": "claim", "benefit_class": "general", "provider_tier": "in_network_clinic", "billed_amount": 1000}
    later = post(client, f"/api/policies/{policy}/servicing", {**body, "event_id": "LATER", "policy_month": 8})
    assert later.status_code == 200, later.text
    assert later.json()["decision"]["plan_pays_fils"] == 40000
    earlier = post(client, f"/api/policies/{policy}/servicing", {**body, "event_id": "EARLIER", "policy_month": 7})
    assert earlier.status_code == 200, earlier.text
    assert earlier.json()["decision"]["plan_pays_fils"] == 40000
    assert earlier.json()["ledger"]["annual_paid_fils"] == 120000
    history = client.get(f"/api/policies/{policy}").json()["servicing"]
    assert [(row["event_id"], row["record_type"], row["plan_pays_fils"]) for row in history] == [
        ("LATER", "decision", 40000),
        ("EARLIER", "decision", 80000),
        ("EARLIER", "revision", 40000),
        ("LATER", "revision", 80000),
    ]
    assert history[2]["supersedes_id"] == history[1]["id"]
    assert history[3]["supersedes_id"] == history[0]["id"]


def test_appeal_appends_an_overturn_revision_and_replays_ledger(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(fixture_client, "plan_b")
    denied = post(
        client,
        f"/api/policies/{policy}/servicing",
        {"event_id": "WAIT-1", "kind": "claim", "policy_month": 1, "benefit_class": "chronic_preexisting", "provider_tier": "in_network_clinic", "billed_amount": 3000},
    )
    assert denied.status_code == 200
    assert denied.json()["decision"]["reason_code"] == "waiting_period_not_elapsed"
    appeal = post(
        client,
        f"/api/policies/{policy}/appeals",
        {"appeal_id": "APL-1", "contested_event_id": "WAIT-1", "statement": "The treatment happened after the waiting period.", "evidence": ["carrier confirmation"]},
    )
    assert appeal.status_code == 200
    assert appeal.json()["status"] == "pending_review"
    queue = broker_get(fixture_client, "/api/broker/appeals").json()
    assert queue[0]["appeal"]["contested_event_id"] == "WAIT-1"
    reviewed = broker_post(
        fixture_client,
        f"/api/broker/appeals/{appeal.json()['appeal']['id']}/review",
        {"action": "overturn", "note": "Evidence confirms month seven.", "corrected_policy_month": 7},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["effective_decision"]["outcome"] == "covered"
    assert reviewed.json()["ledger"]["annual_paid_fils"] > 0
    detail = client.get(f"/api/policies/{policy}").json()
    assert [item["record_type"] for item in detail["servicing"]] == ["decision", "appeal", "appeal_review", "revision"]


def test_appeal_overturn_appends_downstream_revision_without_changing_original(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(fixture_client, "plan_b")
    denied = post(client, f"/api/policies/{policy}/servicing", {"event_id": "EARLY-WAIT", "kind": "claim", "policy_month": 4, "benefit_class": "chronic_preexisting", "provider_tier": "in_network_clinic", "billed_amount": 2800})
    assert denied.json()["decision"]["reason_code"] == "waiting_period_not_elapsed"
    later = post(client, f"/api/policies/{policy}/servicing", {"event_id": "LATER-CARE", "kind": "claim", "policy_month": 7, "benefit_class": "chronic_preexisting", "provider_tier": "in_network_clinic", "billed_amount": 2600})
    assert later.json()["decision"]["plan_pays_fils"] == 168000
    appeal = post(client, f"/api/policies/{policy}/appeals", {"appeal_id": "APPEAL-LATE", "contested_event_id": "EARLY-WAIT", "statement": "The treatment date was recorded incorrectly.", "evidence": ["Verified treatment-date record"]})
    reviewed = broker_post(fixture_client, f"/api/broker/appeals/{appeal.json()['appeal']['id']}/review", {"action": "overturn", "note": "Reviewed the treatment-date record.", "corrected_policy_month": 6})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["effective_decision"]["plan_pays_fils"] == 184000
    assert reviewed.json()["ledger"]["annual_paid_fils"] == 392000
    history = client.get(f"/api/policies/{policy}").json()["servicing"]
    later_rows = [row for row in history if row["event_id"] == "LATER-CARE"]
    assert [(row["record_type"], row["plan_pays_fils"]) for row in later_rows] == [
        ("decision", 168000), ("revision", 208000)
    ]
    assert later_rows[1]["supersedes_id"] == later_rows[0]["id"]


def test_app2_provider_evidence_preserves_original_input_and_changes_preauth_forecast(fixture_client):
    client, _, engine = fixture_client
    policy = create_policy(fixture_client, "plan_b")
    events = {event["id"]: event for event in source_data()["servicing_events"]}
    claim = events["CLM-4"]
    denied = post(client, f"/api/policies/{policy}/servicing", {
        "event_id": claim["id"], "kind": "claim", "policy_month": claim["policy_month"],
        "benefit_class": claim["benefit_class"], "provider_tier": claim["provider_tier"],
        "setting": claim["setting"], "billed_amount": claim["billed_amount"],
    })
    assert denied.json()["decision"]["reason_code"] == "provider_out_of_network"
    evidence = events["APP-2"]["evidence_attached"][0]
    appeal = post(client, f"/api/policies/{policy}/appeals", {
        "appeal_id": "APP-2", "contested_event_id": "CLM-4",
        "statement": events["APP-2"]["applicant_claim"], "evidence": [evidence],
    }).json()
    review = broker_post(fixture_client, f"/api/broker/appeals/{appeal['appeal']['id']}/review", {
        "action": "overturn", "note": "Registration supports independent standard-network membership.",
        "verified_network_membership": {
            "provider_name": "Gulf Physiotherapy Centre LLC",
            "network_tier": "standard", "evidence_reference": evidence,
        },
    })
    assert review.status_code == 200, review.text
    assert review.json()["effective_decision"]["plan_pays_fils"] == 440000
    assert review.json()["ledger"]["deductible_met_fils"] == 50000
    with Session(engine) as db:
        original = db.scalar(select(ServicingEvent).where(ServicingEvent.policy_id == policy, ServicingEvent.root_id == "CLM-4", ServicingEvent.record_type == "decision"))
        revision = db.scalar(select(ServicingEvent).where(ServicingEvent.policy_id == policy, ServicingEvent.root_id == "CLM-4", ServicingEvent.record_type == "revision"))
        assert original.payload["provider_tier"] == "top_tier_private_hospital"
        assert revision.payload["provider_tier"] == "top_tier_private_hospital"
        assert revision.payload["verified_network_membership"]["evidence_reference"] == evidence
    pre = events["PRE-2"]
    forecast = client.post(f"/api/policies/{policy}/servicing/preview", json={
        "event_id": pre["id"], "kind": "preauth", "policy_month": pre["policy_month"],
        "benefit_class": pre["benefit_class"], "provider_tier": pre["provider_tier"],
        "setting": pre["setting"], "estimated_amount": pre["estimated_amount"],
    })
    assert forecast.status_code == 200, forecast.text
    assert forecast.json()["decision"]["plan_pays_fils"] == 2240000


def test_reassessment_requires_and_records_a_broker_review(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(fixture_client)
    reassessment = post(client, f"/api/policies/{policy}/reassess", {})
    assert reassessment.status_code == 200
    queue = broker_get(fixture_client, "/api/broker/reassessments").json()
    assert queue[0]["status"] == "pending_review"
    review = broker_post(
        fixture_client,
        f"/api/broker/reassessments/{queue[0]['id']}/review",
        {"action": "retain", "note": "Current fictional plan remains supported by saved facts."},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "reviewed"


def test_appeal_accepts_only_denied_financial_decisions_and_requires_evidence_to_overturn(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(fixture_client, "plan_b")
    covered = post(client, f"/api/policies/{policy}/servicing", {
        "event_id": "COVERED", "kind": "claim", "policy_month": 7,
        "benefit_class": "general", "provider_tier": "in_network_clinic", "billed_amount": 1000,
    })
    assert covered.json()["decision"]["outcome"] == "covered"
    preauth = post(client, f"/api/policies/{policy}/servicing", {
        "event_id": "DECLINED-PRE", "kind": "preauth", "policy_month": 1,
        "benefit_class": "chronic_preexisting", "provider_tier": "in_network_clinic", "estimated_amount": 1000,
    })
    assert preauth.json()["decision"]["outcome"] == "declined"
    for event_id in ("COVERED", "DECLINED-PRE"):
        invalid = post(client, f"/api/policies/{policy}/appeals", {
            "appeal_id": f"APPEAL-{event_id}", "contested_event_id": event_id,
            "statement": "Please review this decision.",
        })
        assert invalid.status_code == 422, invalid.text

    denied = post(client, f"/api/policies/{policy}/servicing", {
        "event_id": "WAIT-NO-EVIDENCE", "kind": "claim", "policy_month": 1,
        "benefit_class": "chronic_preexisting", "provider_tier": "in_network_clinic", "billed_amount": 1000,
    })
    assert denied.json()["decision"]["outcome"] == "denied"
    body = {"appeal_id": "APPEAL-NO-EVIDENCE", "contested_event_id": "WAIT-NO-EVIDENCE", "statement": "I disagree with the recorded month."}
    appeal = post(client, f"/api/policies/{policy}/appeals", body)
    assert appeal.status_code == 200, appeal.text
    duplicate = post(client, f"/api/policies/{policy}/appeals", {**body, "appeal_id": "ANOTHER-APPEAL"})
    assert duplicate.status_code == 409
    appeal_id = appeal.json()["appeal"]["id"]
    rejected = broker_post(fixture_client, f"/api/broker/appeals/{appeal_id}/review", {
        "action": "overturn", "note": "No independent evidence was attached.", "corrected_policy_month": 7,
    })
    assert rejected.status_code == 422, rejected.text
    upheld = broker_post(fixture_client, f"/api/broker/appeals/{appeal_id}/review", {
        "action": "uphold", "note": "The recorded waiting period still applies.",
    })
    assert upheld.status_code == 200, upheld.text
    repeated = post(client, f"/api/policies/{policy}/appeals", body)
    assert repeated.json()["status"] == "reviewed"
