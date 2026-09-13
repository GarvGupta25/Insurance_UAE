from datetime import date, timedelta
from uuid import uuid4


def post(client, path, body):
    return client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})


def create_policy(client, plan_id="plan_a"):
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
    application = post(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": plan_id}).json()["id"]
    preview = client.get(f"/api/applications/{application}").json()
    assert post(
        client,
        f"/api/broker/recommendations/{preview['recommendation_id']}/review",
        {"action": "approve", "note": "Synthetic broker review."},
    ).status_code == 200
    preview = client.get(f"/api/applications/{application}").json()
    return post(client, f"/api/applications/{application}/submit", {"payload_hash": preview["payload_hash"], "declarations_confirmed": True}).json()["policy_id"]


def test_servicing_endpoint_persists_claim_and_keeps_forecast_out_of_ledger(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(client)
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


def test_servicing_preview_is_read_only_and_rejects_a_stale_confirmation(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(client)
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
    policy = create_policy(client, "plan_b")
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
    policy = create_policy(client, "plan_b")
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
    queue = client.get("/api/broker/appeals").json()
    assert queue[0]["appeal"]["contested_event_id"] == "WAIT-1"
    reviewed = post(
        client,
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
    policy = create_policy(client, "plan_b")
    denied = post(client, f"/api/policies/{policy}/servicing", {"event_id": "EARLY-WAIT", "kind": "claim", "policy_month": 4, "benefit_class": "chronic_preexisting", "provider_tier": "in_network_clinic", "billed_amount": 2800})
    assert denied.json()["decision"]["reason_code"] == "waiting_period_not_elapsed"
    later = post(client, f"/api/policies/{policy}/servicing", {"event_id": "LATER-CARE", "kind": "claim", "policy_month": 7, "benefit_class": "chronic_preexisting", "provider_tier": "in_network_clinic", "billed_amount": 2600})
    assert later.json()["decision"]["plan_pays_fils"] == 168000
    appeal = post(client, f"/api/policies/{policy}/appeals", {"appeal_id": "APPEAL-LATE", "contested_event_id": "EARLY-WAIT", "statement": "The treatment date was recorded incorrectly.", "evidence": ["Verified treatment-date record"]})
    reviewed = post(client, f"/api/broker/appeals/{appeal.json()['appeal']['id']}/review", {"action": "overturn", "note": "Reviewed the treatment-date record.", "corrected_policy_month": 6})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["effective_decision"]["plan_pays_fils"] == 184000
    assert reviewed.json()["ledger"]["annual_paid_fils"] == 392000
    history = client.get(f"/api/policies/{policy}").json()["servicing"]
    later_rows = [row for row in history if row["event_id"] == "LATER-CARE"]
    assert [(row["record_type"], row["plan_pays_fils"]) for row in later_rows] == [
        ("decision", 168000), ("revision", 208000)
    ]
    assert later_rows[1]["supersedes_id"] == later_rows[0]["id"]


def test_reassessment_requires_and_records_a_broker_review(fixture_client):
    client, _, _ = fixture_client
    policy = create_policy(client)
    reassessment = post(client, f"/api/policies/{policy}/reassess", {})
    assert reassessment.status_code == 200
    queue = client.get("/api/broker/reassessments").json()
    assert queue[0]["status"] == "pending_review"
    review = post(
        client,
        f"/api/broker/reassessments/{queue[0]['id']}/review",
        {"action": "retain", "note": "Current fictional plan remains supported by saved facts."},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "reviewed"
