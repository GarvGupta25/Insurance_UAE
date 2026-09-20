from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import User
from app.marketplace_models import MarketplacePolicy, Provider, ProviderUser
from app.models import BrokerAssignment, Case, Profile, Quote, Recommendation, ReviewDecision
from scripts.seed_marketplace_providers import seed_catalogue

PROFILE = {
    "legal_name": "Fresh Synthetic Member",
    "date_of_birth": "1991-04-16",
    "nationality": "Indian",
    "residency": "resident",
    "emirate": "Dubai",
    "emirates_id_status": "issued",
    "diagnosed_conditions": "no",
    "conditions": [],
    "smoker": "no",
    "maternity": False,
    "geography": "UAE",
    "start_date": "2026-10-01",
    "near_term_needs": [],
    "payer": "self",
    "annual_budget": 12000,
    "strict_budget": False,
    "payment_frequency": "monthly",
    "preferred_network": "standard",
}


def quotation(premium: int) -> dict:
    return {
        "premium": premium,
        "plan_terms": {
            "name": f"Submitted marketplace quote {premium}",
            "network": "standard",
            "annual_limit": 500000,
            "deductible": 500,
            "outpatient_copay_pct": 20,
            "maternity": {"covered": True, "waiting_period_months": 6, "limit": 50000},
            "chronic_preexisting": {"covered": True, "waiting_period_months": 0},
        },
    }


def test_seeded_catalogue_completes_the_full_marketplace_journey(fixture_client):
    client, owner, engine = fixture_client
    member = owner[0]
    broker_id = str(uuid4())
    case_id = "phase-8-full-journey"
    provider_accounts = {}

    with Session(engine) as db:
        seed_catalogue(db)
        db.add_all(
            [
                Profile(owner_id=member.id, facts=PROFILE),
                Case(id=case_id, owner_id=member.id, status="open"),
                BrokerAssignment(member_id=member.id, broker_id=broker_id),
            ]
        )
        db.flush()
        quote = Quote(owner_id=member.id, case_id=case_id, profile_version=1, snapshot={})
        db.add(quote)
        db.flush()
        recommendation = Recommendation(
            owner_id=member.id,
            case_id=case_id,
            quote_id=quote.id,
            profile_version=1,
            proposed_plan_id="plan_a",
            status="approved",
        )
        db.add(recommendation)
        db.flush()
        db.add(
            ReviewDecision(
                owner_id=broker_id,
                recommendation_id=recommendation.id,
                action="approve",
                note="Checkpoint 1: profile and recommendation verified.",
            )
        )
        for provider in db.scalars(
            select(Provider).where(Provider.name != "Helm Direct").order_by(Provider.name)
        ):
            user_id = str(uuid4())
            provider_accounts[provider.id] = User(
                user_id, f"provider@{provider.name.lower().replace(' ', '-')}.test", "provider"
            )
            db.add(ProviderUser(user_id=user_id, provider_id=provider.id, display_name=provider.name))
        db.commit()

    recommendations = client.get(f"/api/marketplace/cases/{case_id}/recommendations")
    assert recommendations.status_code == 200
    assert len(recommendations.json()["recommendations"]) == 5
    assert "send your details" in recommendations.json()["consent_question"]

    consent = client.post(f"/api/marketplace/cases/{case_id}/consent", json={"consent": "yes"})
    assert consent.status_code == 200
    applications = consent.json()["applications"]
    assert len(applications) >= 2
    invited = {row["provider_id"]: row["id"] for row in applications}

    for provider_id, provider_user in provider_accounts.items():
        owner[0] = provider_user
        inbox = client.get("/api/provider/applications")
        assert inbox.status_code == 200
        assert [row["id"] for row in inbox.json()] == ([invited[provider_id]] if provider_id in invited else [])

    for position, (provider_id, application_id) in enumerate(invited.items()):
        owner[0] = provider_accounts[provider_id]
        response = client.post(
            f"/api/provider/applications/{application_id}/quote",
            json=quotation(7600 + position * 900),
        )
        assert response.status_code == 201

    owner[0] = member
    comparison = client.get(f"/api/marketplace/cases/{case_id}/quotations")
    assert comparison.status_code == 200
    assert comparison.json()["collection_ready"] is True
    assert len(comparison.json()["quotations"]) == min(3, len(invited))
    assert [row["rank"] for row in comparison.json()["quotations"]] == list(
        range(1, len(comparison.json()["quotations"]) + 1)
    )
    selected = comparison.json()["quotations"][0]
    assert client.post(f"/api/marketplace/quotations/{selected['quotation_id']}/select").status_code == 200

    selected_provider_id = next(
        provider_id for provider_id, application_id in invited.items() if application_id == selected["application_id"]
    )
    owner[0] = provider_accounts[selected_provider_id]
    assert client.post(f"/api/provider/quotations/{selected['quotation_id']}/accept").status_code == 200
    assert client.post(f"/api/provider/policies/{selected['quotation_id']}/start").status_code == 403

    owner[0] = User(broker_id, "phase-8-broker@example.test", "broker")
    checkpoint = client.post(
        f"/api/broker/marketplace/applications/{selected['application_id']}/checkpoint-2",
        json={"action": "approve", "note": "Checkpoint 2: accepted provider terms verified."},
    )
    assert checkpoint.status_code == 200

    owner[0] = provider_accounts[selected_provider_id]
    started = client.post(f"/api/provider/policies/{selected['quotation_id']}/start")
    assert started.status_code == 201
    policy_id = started.json()["id"]
    assert [row["id"] for row in client.get("/api/provider/policies").json()] == [policy_id]

    for provider_id, provider_user in provider_accounts.items():
        if provider_id == selected_provider_id:
            continue
        owner[0] = provider_user
        assert client.get("/api/provider/policies").json() == []
        assert client.get(f"/api/provider/policies/{policy_id}/payments").status_code == 404

    owner[0] = member
    assert [row["id"] for row in client.get("/api/marketplace/policies").json()] == [policy_id]
    owner[0] = User(str(uuid4()), "unrelated-member@example.test")
    assert client.get("/api/marketplace/policies").json() == []

    owner[0] = User(broker_id, "phase-8-broker@example.test", "broker")
    case = client.get(f"/api/broker/cases/{member.id}")
    assert case.status_code == 200
    assert [row["id"] for row in case.json()["marketplace_policies"]] == [policy_id]
    with Session(engine) as db:
        assert db.scalar(select(MarketplacePolicy).where(MarketplacePolicy.id == policy_id)) is not None
