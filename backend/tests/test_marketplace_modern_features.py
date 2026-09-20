from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth import User
from app.marketplace_matching import create_consented_applications
from app.marketplace_models import MarketplaceApplication, Provider, ProviderQuotation
from app.models import (
    BrokerAssignment,
    Case,
    Quote,
    Recommendation,
    ReviewDecision,
    now,
)


def approve_case(db: Session, owner_id: str, case_id: str):
    quote = Quote(owner_id=owner_id, case_id=case_id, profile_version=1, snapshot={})
    db.add(quote)
    db.flush()
    recommendation = Recommendation(
        owner_id=owner_id,
        case_id=case_id,
        quote_id=quote.id,
        profile_version=1,
        proposed_plan_id="seed-plan",
        status="approved",
    )
    db.add(recommendation)
    db.flush()
    db.add(
        ReviewDecision(
            owner_id="broker-reviewer",
            recommendation_id=recommendation.id,
            action="approve",
        )
    )
    db.flush()


def test_near_duplicate_application_enters_existing_broker_worklist(fixture_client):
    client, owner, engine = fixture_client
    member, broker_id = owner[0], str(uuid4())
    with Session(engine) as db:
        db.add(Provider(id="duplicate-provider", name="Duplicate Provider"))
        db.add(BrokerAssignment(member_id=member.id, broker_id=broker_id))
        for case_id in ("duplicate-case-a", "duplicate-case-b"):
            db.add(Case(id=case_id, owner_id=member.id, status="open"))
            db.flush()
            approve_case(db, member.id, case_id)
            create_consented_applications(
                db,
                owner_id=member.id,
                case_id=case_id,
                profile={"age": 34, "annual_budget": 12000},
                ranked=[{"plan_id": "seed-plan", "provider_id": "duplicate-provider"}],
                consent="yes",
            )
        db.commit()

    owner[0] = User(broker_id, "broker@example.test", "broker")
    response = client.get("/api/broker/worklist")
    duplicate_items = [
        row
        for row in response.json()
        if row["item_type"] == "provider_flag" and "near-duplicate" in row["priority_reason"]
    ]
    assert response.status_code == 200
    assert len(duplicate_items) == 1
    assert duplicate_items[0]["case_id"] == "duplicate-case-b"


def test_provider_performance_uses_existing_timestamps_and_shows_pearl_fastest(fixture_client):
    client, owner, engine = fixture_client
    broker_id, sent_at = str(uuid4()), now() - timedelta(days=1)
    with Session(engine) as db:
        for position, (name, hours, status) in enumerate(
            (
                ("Pearl Health Partners", 2, "selected"),
                ("Al Noor Takaful", 12, "declined"),
                ("Gulf Shield Insurance", 18, "declined"),
            ),
            1,
        ):
            provider = Provider(id=f"performance-provider-{position}", name=name)
            case = Case(id=f"performance-case-{position}", owner_id=f"member-{position}", status="open")
            application = MarketplaceApplication(
                id=f"performance-application-{position}",
                owner_id=f"member-{position}",
                case_id=case.id,
                provider_id=provider.id,
                status="customer_selected" if status == "selected" else "declined",
                created_at=sent_at,
            )
            db.add_all((provider, case, application))
            db.flush()
            db.add(
                ProviderQuotation(
                    application_id=application.id,
                    provider_id=provider.id,
                    plan_terms={},
                    premium=Decimal("9000"),
                    status=status,
                    submitted_at=sent_at + timedelta(hours=hours),
                )
            )
        db.commit()

    owner[0] = User(broker_id, "broker@example.test", "broker")
    response = client.get("/api/broker/marketplace/provider-performance")
    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["provider_name"] == "Pearl Health Partners"
    assert rows[0]["average_turnaround_hours"] == 2
    assert rows[0]["win_rate_pct"] == 100
    assert [row["average_turnaround_hours"] for row in rows] == [2, 12, 18]
