from datetime import timedelta
from decimal import Decimal

from conftest import as_assigned_broker
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.marketplace_models import MarketplaceApplication, Provider, ProviderQuotation
from app.models import Case, Quote, Recommendation, ReviewDecision, now


def seed_application(fixture_client, *, ident: str, status: str, age_days: int = 0):
    _, owner, engine = fixture_client
    member = owner[0]
    with Session(engine) as db:
        case = Case(id=f"case-{ident}", owner_id=member.id, status="open")
        provider = Provider(id=f"provider-{ident}", name=f"Provider {ident}")
        application = MarketplaceApplication(
            id=ident,
            owner_id=member.id,
            case_id=case.id,
            provider_id=provider.id,
            status=status,
            created_at=now() - timedelta(days=age_days),
        )
        db.add_all((case, provider, application))
        db.commit()
    return ident, f"case-{ident}", f"provider-{ident}"


def approve_checkpoint_one(fixture_client, case_id: str):
    _, owner, engine = fixture_client
    member = owner[0]
    with Session(engine) as db:
        quote = Quote(owner_id=member.id, case_id=case_id, profile_version=1, snapshot={})
        db.add(quote)
        db.flush()
        recommendation = Recommendation(
            owner_id=member.id,
            case_id=case_id,
            quote_id=quote.id,
            profile_version=1,
            proposed_plan_id="plan-a",
            status="approved",
        )
        db.add(recommendation)
        db.flush()
        db.add(
            ReviewDecision(
                owner_id="checkpoint-one-broker",
                recommendation_id=recommendation.id,
                action="approve",
            )
        )
        db.commit()


def test_direct_send_without_checkpoint_one_is_rejected(fixture_client):
    client, owner, engine = fixture_client
    application_id, _, _ = seed_application(
        fixture_client, ident="send-without-review", status="broker_approved"
    )

    with as_assigned_broker(owner, engine):
        response = client.post(f"/api/broker/marketplace/applications/{application_id}/send")

    assert response.status_code == 403
    with Session(engine) as db:
        assert db.get(MarketplaceApplication, application_id).status == "broker_approved"


def test_binding_requires_a_separate_checkpoint_two(fixture_client):
    client, owner, engine = fixture_client
    application_id, case_id, provider_id = seed_application(
        fixture_client, ident="binding-guard", status="provider_accepted"
    )
    approve_checkpoint_one(fixture_client, case_id)
    with Session(engine) as db:
        db.add(
            ProviderQuotation(
                application_id=application_id,
                provider_id=provider_id,
                plan_terms={"deductible": 500},
                premium=Decimal("9000.00"),
                status="accepted",
            )
        )
        db.commit()

    with as_assigned_broker(owner, engine):
        rejected = client.post(
            f"/api/broker/marketplace/applications/{application_id}/binding-readiness"
        )
        approved = client.post(
            f"/api/broker/marketplace/applications/{application_id}/checkpoint-2",
            json={"action": "approve", "note": "Final terms checked."},
        )
        ready = client.post(
            f"/api/broker/marketplace/applications/{application_id}/binding-readiness"
        )

    assert rejected.status_code == 403
    assert approved.status_code == 200
    assert ready.status_code == 200
    with Session(engine) as db:
        reviews = db.scalars(
            select(ReviewDecision).where(
                ReviewDecision.marketplace_application_id == application_id
            )
        ).all()
        assert [(review.checkpoint, review.action) for review in reviews] == [
            ("checkpoint_2", "approve")
        ]


def test_worklist_unions_both_marketplace_checkpoints_oldest_first(fixture_client):
    client, owner, engine = fixture_client
    seed_application(
        fixture_client,
        ident="checkpoint-one-item",
        status="awaiting_broker_review",
        age_days=2,
    )
    seed_application(
        fixture_client,
        ident="checkpoint-two-item",
        status="provider_accepted",
        age_days=5,
    )

    with as_assigned_broker(owner, engine):
        response = client.get("/api/broker/worklist")

    assert response.status_code == 200
    marketplace = [
        item for item in response.json() if item["item_type"].startswith("marketplace_checkpoint")
    ]
    assert [item["item_type"] for item in marketplace] == [
        "marketplace_checkpoint_2",
        "marketplace_checkpoint_1",
    ]
