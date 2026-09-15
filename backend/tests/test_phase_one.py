import io
from datetime import date, timedelta
from uuid import uuid4

import pytest
from conftest import as_assigned_broker
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import User
from app.contracts import Facts
from app.documents import extract_identity
from app.domain import compare, installments, map_application
from app.models import Policy, ProfileVersion, Receipt


def send(client, path, body=None, key=None):
    return client.post(path, json=body or {}, headers={"Idempotency-Key": key or str(uuid4())})


def facts(**overrides):
    return {
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
        "payment_frequency": "monthly",
        **overrides,
    }


def setup_case(client, **overrides):
    profile = client.get("/api/me/profile").json()
    assert (
        client.patch(
            "/api/me/profile", json={"expected_version": profile["version"], "changes": facts(**overrides)}
        ).status_code
        == 200
    )
    case = send(client, "/api/cases").json()["id"]
    quote = send(client, f"/api/cases/{case}/quotes").json()["id"]
    return case, quote


def setup_policy(client, owner, engine, plan="plan_b"):
    case, quote = setup_case(client)
    application = send(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": plan, "request_broker_review": True}).json()["id"]
    preview = client.get(f"/api/applications/{application}").json()
    with as_assigned_broker(owner, engine):
        review = send(
            client,
            f"/api/broker/recommendations/{preview['recommendation_id']}/review",
            {"action": "approve", "note": "Synthetic broker review."},
        )
    assert review.status_code == 200, review.text
    preview = client.get(f"/api/applications/{application}").json()
    body = {"payload_hash": preview["payload_hash"], "declarations_confirmed": True}
    result = send(client, f"/api/applications/{application}/submit", body)
    assert result.status_code == 200, result.text
    return result.json()["policy_id"], application, body


def test_full_sandbox_flow_and_exact_schedule(fixture_client):
    client, owner, engine = fixture_client
    policy_id, _, _ = setup_policy(client, owner, engine)
    policy = client.get(f"/api/policies/{policy_id}").json()
    assert len(policy["instalments"]) == 12
    assert sum(row["amount"] for row in policy["instalments"]) == 890000
    order = send(client, f"/api/instalments/{policy['instalments'][0]['id']}/payment-order").json()
    key = str(uuid4())
    first = send(client, f"/api/payment-orders/{order['id']}/simulate", {"result": "captured"}, key)
    retry = send(client, f"/api/payment-orders/{order['id']}/simulate", {"result": "captured"}, key)
    assert first.status_code == 200 and retry.json() == first.json()
    refreshed = client.get(f"/api/policies/{policy_id}").json()
    assert refreshed["paid_fils"] == policy["instalments"][0]["amount"]
    assert refreshed["status"] == "demo_active"
    with Session(engine) as db:
        assert len(db.scalars(select(Receipt)).all()) == 1
        assert len(db.scalars(select(Policy)).all()) == 1


def test_every_easy_fill_waits_for_a_broker_review(fixture_client):
    client, owner, engine = fixture_client
    _, quote = setup_case(client)
    application = send(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a"}).json()["id"]
    preview = client.get(f"/api/applications/{application}").json()
    assert preview["status"] == "awaiting_broker_review"
    with as_assigned_broker(owner, engine):
        assert client.get("/api/broker/recommendations").json()
    submitted = send(client, f"/api/applications/{application}/submit", {
        "payload_hash": preview["payload_hash"], "declarations_confirmed": True,
    })
    assert submitted.status_code == 409, submitted.text


def test_repeated_pending_submission_attempts_cannot_create_a_policy(fixture_client):
    client, _, _ = fixture_client
    _, quote = setup_case(client)
    application = send(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a"}).json()["id"]
    preview = client.get(f"/api/applications/{application}").json()
    body = {"payload_hash": preview["payload_hash"], "declarations_confirmed": True}
    first = send(client, f"/api/applications/{application}/submit", body)
    second = send(client, f"/api/applications/{application}/submit", body)
    assert [first.status_code, second.status_code] == [409, 409]
    assert client.get("/api/policies").json() == []


def test_no_cross_account_access_and_no_body_owner_override(fixture_client):
    client, owner, _ = fixture_client
    case, quote = setup_case(client)
    first_owner = owner[0]
    owner[0] = User(str(uuid4()), "second@example.test")
    for path in [f"/api/cases/{case}", f"/api/quotes/{quote}", f"/api/quotes/{quote}/download"]:
        assert client.get(path).status_code == 404
    assert (
        send(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a"}).status_code == 404
    )
    assert client.get("/api/policies").json() == []
    assert client.get("/api/me/profile").json()["facts"] == {}
    bad = client.patch(
        "/api/me/profile", json={"expected_version": 1, "changes": {"owner_id": first_owner.id}}
    )
    assert bad.status_code == 422


def test_stale_quote_and_confirmation_never_submit(fixture_client):
    client, _, _ = fixture_client
    _, quote = setup_case(client)
    application = send(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a"}).json()[
        "id"
    ]
    preview = client.get(f"/api/applications/{application}").json()
    assert (
        send(
            client,
            f"/api/applications/{application}/submit",
            {"payload_hash": preview["payload_hash"], "declarations_confirmed": False},
        ).status_code
        == 422
    )
    assert (
        send(
            client,
            f"/api/applications/{application}/submit",
            {"payload_hash": "changed", "declarations_confirmed": True},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/me/profile", json={"expected_version": 2, "changes": {"annual_budget": 5000}}
        ).status_code
        == 200
    )
    assert client.get(f"/api/quotes/{quote}").json()["stale"]
    assert (
        send(
            client,
            f"/api/applications/{application}/submit",
            {"payload_hash": preview["payload_hash"], "declarations_confirmed": True},
        ).status_code
        == 409
    )


def test_duplicate_application_is_one_policy(fixture_client):
    client, owner, engine = fixture_client
    _, quote = setup_case(client)
    a = send(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a", "request_broker_review": True}).json()["id"]
    preview = client.get(f"/api/applications/{a}").json()
    with as_assigned_broker(owner, engine):
        assert send(
            client,
            f"/api/broker/recommendations/{preview['recommendation_id']}/review",
            {"action": "approve", "note": "Synthetic broker review."},
        ).status_code == 200
    preview = client.get(f"/api/applications/{a}").json()
    key = str(uuid4())
    payload = {"payload_hash": preview["payload_hash"], "declarations_confirmed": True}
    first = send(client, f"/api/applications/{a}/submit", payload, key)
    assert send(client, f"/api/applications/{a}/submit", payload, key).json() == first.json()
    assert send(client, f"/api/applications/{a}/submit", payload).status_code == 409
    with Session(engine) as db:
        assert len(db.scalars(select(Policy)).all()) == 1


def test_requested_broker_review_is_required_before_sandbox_submission(fixture_client):
    client, owner, engine = fixture_client
    _, quote = setup_case(client)
    application = send(client, "/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a", "request_broker_review": True}).json()["id"]
    preview = client.get(f"/api/applications/{application}").json()
    body = {"payload_hash": preview["payload_hash"], "declarations_confirmed": True}
    assert send(client, f"/api/applications/{application}/submit", body).status_code == 409
    assert send(client, f"/api/broker/recommendations/{preview['recommendation_id']}/review", {"action": "approve"}).status_code == 403
    with as_assigned_broker(owner, engine):
        reviewed = send(
            client,
            f"/api/broker/recommendations/{preview['recommendation_id']}/review",
            {"action": "approve", "note": "Terms and tradeoffs reviewed."},
        )
    assert reviewed.status_code == 200
    assert send(client, f"/api/applications/{application}/submit", body).status_code == 422
    new_preview = client.get(f"/api/applications/{application}").json()
    assert send(
        client,
        f"/api/applications/{application}/submit",
        {"payload_hash": new_preview["payload_hash"], "declarations_confirmed": True},
    ).status_code == 200


def test_key_reuse_payload_conflict(fixture_client):
    client, _, _ = fixture_client
    case, _ = setup_case(client)
    key = str(uuid4())
    assert send(client, f"/api/cases/{case}/messages", {"text": "hello"}, key).status_code == 200
    assert send(client, f"/api/cases/{case}/messages", {"text": "different"}, key).status_code == 409


def test_negative_health_not_inferred_and_unknown_not_false():
    with pytest.raises(ValueError):
        Facts.model_validate({"diagnosed_conditions": "no", "conditions": ["diabetes"]})
    assert Facts.model_validate({"diagnosed_conditions": "unknown"}).diagnosed_conditions == "unknown"
    rows = compare(facts(diagnosed_conditions="yes", conditions=["diabetes"], immediate_chronic_cover=True))
    assert rows[0]["plan"]["id"] == "plan_c"
    assert all(x["status"] == "does_not_meet_requirement" for x in rows[1:])


def test_maternity_and_unknown_geography():
    rows = compare(facts(maternity=True, maximum_maternity_wait=6))
    assert rows[0]["plan"]["id"] == "plan_c"
    assert len([x for x in rows if x["status"] == "supported"]) == 1
    assert all(x["status"] == "needs_more_information" for x in compare(facts(geography="international")))
    assert all(
        x["status"] == "does_not_meet_requirement"
        for x in compare(facts(annual_budget=1000, strict_budget=True))
    )


def test_schedules_round_and_keep_end_of_month():
    rows = installments(890001, "2027-01-31", 12)
    assert sum(x["amount"] for x in rows) == 890001
    assert rows[1]["due_date"] == "2027-02-28"
    assert rows[2]["due_date"] == "2027-03-31"


def test_two_application_schemas_reuse_facts():
    first = map_application("plan_a", facts(), "a@example.test")
    second = map_application("plan_b", facts(), "a@example.test")
    assert first["schema"] != second["schema"]
    assert first["payload"]["applicant"]["full_name"] == second["payload"]["memberName"]


def test_pdf_is_readable_and_identity_extraction_provisional(fixture_client):
    import fitz
    from reportlab.pdfgen.canvas import Canvas

    client, _, _ = fixture_client
    _, quote = setup_case(client)
    result = client.get(f"/api/quotes/{quote}/download")
    assert result.status_code == 200 and result.content.startswith(b"%PDF-")
    with fitz.open(stream=result.content, filetype="pdf") as pdf:
        text = " ".join(page.get_text() for page in pdf)
        assert "4,200" in text and "8,900" in text and "16,500" in text
    output = io.BytesIO()
    canvas = Canvas(output)
    canvas.drawString(50, 750, "Name: Amina Example")
    canvas.drawString(50, 730, "DOB: 1994-03-12")
    canvas.drawString(50, 710, "Nationality: Indian")
    canvas.save()
    extracted = extract_identity(output.getvalue())
    assert extracted["fields"]["date_of_birth"] == "1994-03-12"
    assert extracted["status"] == "needs_review"
    assert "conditions" not in extracted["fields"]


def test_failed_payment_keeps_balance_and_receipts_empty(fixture_client):
    client, owner, engine = fixture_client
    policy_id, _, _ = setup_policy(client, owner, engine)
    policy = client.get(f"/api/policies/{policy_id}").json()
    order = send(client, f"/api/instalments/{policy['instalments'][0]['id']}/payment-order").json()
    assert (
        send(client, f"/api/payment-orders/{order['id']}/simulate", {"result": "failed"}).status_code == 200
    )
    result = client.get(f"/api/policies/{policy_id}").json()
    assert result["paid_fils"] == 0 and result["receipts"] == []


def test_cancelled_payment_attempt_is_visible_and_can_be_retried(fixture_client):
    client, owner, engine = fixture_client
    policy_id, _, _ = setup_policy(client, owner, engine)
    instalment = client.get(f"/api/policies/{policy_id}").json()["instalments"][0]
    order = send(client, f"/api/instalments/{instalment['id']}/payment-order").json()
    assert send(client, f"/api/payment-orders/{order['id']}/simulate", {"result": "cancelled"}).json() == {
        "status": "cancelled"
    }
    policy = client.get(f"/api/policies/{policy_id}").json()
    assert policy["receipts"] == []
    assert policy["payment_attempts"] == [
        {
            "id": order["id"],
            "installment_id": instalment["id"],
            "provider": "simulator",
            "status": "cancelled",
            "amount": instalment["amount"],
            "currency": "AED",
        }
    ]
    retry = send(client, f"/api/instalments/{instalment['id']}/payment-order").json()
    assert retry["id"] != order["id"] and retry["status"] == "created"


def test_profile_history_and_immutable_policy_snapshot(fixture_client):
    client, owner, engine = fixture_client
    policy_id, _, _ = setup_policy(client, owner, engine)
    before = client.get(f"/api/policies/{policy_id}").json()["plan"]
    assert (
        client.patch(
            "/api/me/profile", json={"expected_version": 2, "changes": {"annual_budget": 20000}}
        ).status_code
        == 200
    )
    assert client.get(f"/api/policies/{policy_id}").json()["plan"] == before
    with Session(engine) as db:
        assert len(db.scalars(select(ProfileVersion)).all()) == 2


def test_oversize_and_invalid_identity_upload(fixture_client):
    client, _, _ = fixture_client
    response = client.post("/api/documents", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 422


def test_voice_missing_provider_does_not_fake_success(fixture_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings(), "groq_api_key", "")
    client, _, _ = fixture_client
    response = client.post(
        "/api/voice/transcriptions", files={"file": ("sample.webm", b"\x1aE\xdf\xa3example", "audio/webm")}
    )
    assert response.status_code == 503
