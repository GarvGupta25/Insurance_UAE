from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth import User
from app.marketplace_models import (
    MarketplaceApplication,
    MarketplacePolicy,
    Provider,
    ProviderPayment,
    ProviderQuotation,
    ProviderUser,
)
from app.models import Case, ReviewDecision


def quotation_body(premium=9000):
    return {
        "premium": premium,
        "plan_terms": {
            "network": "wide",
            "annual_limit": 500000,
            "deductible": 300,
            "outpatient_copay_pct": 15,
            "maternity": {"covered": True, "waiting_period_months": 6, "limit": 50000},
            "chronic_preexisting": {"covered": True, "waiting_period_months": 0},
        },
    }


def seed_provider_world(fixture_client):
    _, owner, engine = fixture_client
    member = owner[0]
    provider_user_a = str(uuid4())
    provider_user_b = str(uuid4())
    with Session(engine) as db:
        providers = [
            Provider(id="provider-a", name="Provider A"),
            Provider(id="provider-b", name="Provider B"),
        ]
        db.add_all(providers)
        db.add_all(
            [
                ProviderUser(user_id=provider_user_a, provider_id="provider-a", display_name="A User"),
                ProviderUser(user_id=provider_user_b, provider_id="provider-b", display_name="B User"),
            ]
        )
        for suffix, provider_id in (("a", "provider-a"), ("b", "provider-b")):
            case = Case(id=f"provider-case-{suffix}", owner_id=member.id, status="open")
            application = MarketplaceApplication(
                id=f"provider-application-{suffix}",
                owner_id=member.id,
                case_id=case.id,
                provider_id=provider_id,
                status="sent_to_providers",
                consent_snapshot={"emirate": "Dubai", "budget": 12000, "missing_note": ""},
            )
            db.add_all((case, application))
        db.flush()
        quote_b = ProviderQuotation(
            id="provider-quotation-b",
            application_id="provider-application-b",
            provider_id="provider-b",
            plan_terms={"deductible": 500},
            premium=Decimal("9200.00"),
            status="accepted",
        )
        policy_b = MarketplacePolicy(
            id="provider-policy-b",
            owner_id=member.id,
            application_id="provider-application-b",
            quotation_id=quote_b.id,
            provider_id="provider-b",
        )
        db.add_all((quote_b, policy_b))
        db.flush()
        db.add(
            ProviderPayment(
                owner_id=member.id,
                policy_id=policy_b.id,
                amount=Decimal("9200.00"),
                status="paid",
            )
        )
        db.commit()
    return member, provider_user_a, provider_user_b


def test_every_provider_endpoint_is_tenant_scoped(fixture_client):
    client, owner, _ = fixture_client
    _, provider_user_a, _ = seed_provider_world(fixture_client)
    owner[0] = User(provider_user_a, "a@provider.test", "provider")

    applications = client.get("/api/provider/applications")
    quotations = client.get("/api/provider/quotations")
    policies = client.get("/api/provider/policies")

    assert applications.status_code == 200
    assert [row["id"] for row in applications.json()] == ["provider-application-a"]
    assert quotations.status_code == 200 and quotations.json() == []
    assert policies.status_code == 200 and policies.json() == []

    attempts = [
        client.post(
            "/api/provider/applications/provider-application-b/quote",
            json=quotation_body(),
        ),
        client.post("/api/provider/quotations/provider-quotation-b/accept"),
        client.post("/api/provider/policies/provider-quotation-b/start"),
        client.post(
            "/api/provider/policies/provider-policy-b/discontinue",
            json={"reason": "Requested by policyholder"},
        ),
        client.get("/api/provider/policies/provider-policy-b/payments"),
        client.post(
            "/api/provider/policies/provider-policy-b/flags",
            json={"reason": "Payment anomaly"},
        ),
        client.post(
            "/api/provider/applications/provider-application-b/assistant",
            json={"task": "summarize_application"},
        ),
    ]
    assert [response.status_code for response in attempts] == [404] * len(attempts)


def test_provider_lifecycle_requires_selection_and_checkpoint_two(fixture_client):
    client, owner, engine = fixture_client
    member, provider_user_a, _ = seed_provider_world(fixture_client)
    owner[0] = User(provider_user_a, "a@provider.test", "provider")

    submitted = client.post(
        "/api/provider/applications/provider-application-a/quote",
        json=quotation_body(8800),
    )
    assert submitted.status_code == 201
    quotation_id = submitted.json()["id"]
    assert client.post(f"/api/provider/quotations/{quotation_id}/accept").status_code == 409

    with Session(engine) as db:
        quotation = db.get(ProviderQuotation, quotation_id)
        quotation.status = "selected"
        db.commit()
    accepted = client.post(f"/api/provider/quotations/{quotation_id}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert client.post(f"/api/provider/policies/{quotation_id}/start").status_code == 403

    with Session(engine) as db:
        db.add(
            ReviewDecision(
                owner_id="broker-reviewer",
                marketplace_application_id="provider-application-a",
                checkpoint="checkpoint_2",
                action="approve",
            )
        )
        db.commit()

    started = client.post(f"/api/provider/policies/{quotation_id}/start")
    assert started.status_code == 201
    policy_id = started.json()["id"]
    assert client.get(f"/api/provider/policies/{policy_id}/payments").json() == []
    assert client.post(
        f"/api/provider/policies/{policy_id}/flags",
        json={"reason": "Member details need confirmation", "note": "Broker review requested."},
    ).status_code == 201
    assistant = client.post(
        "/api/provider/applications/provider-application-a/assistant",
        json={"task": "flag_anomalies"},
    )
    assert assistant.status_code == 200
    assert "missing note" in assistant.json()["draft"]
    discontinued = client.post(
        f"/api/provider/policies/{policy_id}/discontinue",
        json={"reason": "Policyholder requested discontinuation"},
    )
    assert discontinued.status_code == 200
    assert discontinued.json()["status"] == "discontinued"


def test_provider_role_requires_a_provider_mapping(fixture_client):
    client, owner, _ = fixture_client
    owner[0] = User(str(uuid4()), "unmapped@provider.test", "provider")
    assert client.get("/api/provider/applications").status_code == 403
