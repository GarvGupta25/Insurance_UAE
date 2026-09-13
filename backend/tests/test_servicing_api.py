from datetime import date, timedelta
from uuid import uuid4


def post(client, path, body):
    return client.post(path, json=body, headers={"Idempotency-Key": str(uuid4())})


def create_policy(client):
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
    case = post(client, "/api/cases", {}) .json()["id"]
    quote = post(client, f"/api/cases/{case}/quotes", {}).json()["id"]
    application = post(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a"}).json()["id"]
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
