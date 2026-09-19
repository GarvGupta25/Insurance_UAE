import json
from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import agents
from app.marketplace_matching import create_consented_applications
from app.marketplace_models import MarketplaceApplication, Provider
from app.models import Base, Case, Quote, Recommendation, ReviewDecision


def plan(plan_id: str, provider_id: str, premium: int, *, network: str = "standard") -> dict:
    return {
        "id": plan_id,
        "plan_code": plan_id,
        "provider_id": provider_id,
        "provider_name": provider_id,
        "name": plan_id,
        "terms": {
            "id": plan_id,
            "name": plan_id,
            "annual_premium": premium,
            "network": network,
            "annual_limit": 500_000,
            "deductible": 500,
            "outpatient_copay_pct": 20,
            "maternity": {"covered": True, "waiting_period_months": 6, "limit": 50_000},
            "chronic_preexisting": {"covered": True, "waiting_period_months": 0},
        },
    }


def test_catalogue_ranking_is_deterministic():
    profile = {
        "annual_budget": 12_000,
        "geography": "UAE",
        "diagnosed_conditions": "no",
        "maternity": False,
        "preferred_network": "standard",
    }
    catalogue = [
        plan("p3", "provider-b", 9_000, network="wide"),
        plan("p1", "provider-a", 8_000),
        plan("p2", "provider-a", 7_000, network="restricted"),
        plan("p4", "provider-c", 11_000),
        plan("p5", "provider-d", 13_000, network="wide"),
        plan("p6", "provider-e", 20_000),
    ]

    first = agents.rank_catalogue_plans(profile, catalogue)
    second = agents.rank_catalogue_plans(profile, catalogue)

    assert first == second
    assert len(first) == 5
    assert [row["rank"] for row in first] == [1, 2, 3, 4, 5]
    assert all(set(row["factors"]) == {"price", "coverage", "network"} for row in first)


def test_plan_with_insufficient_data_never_appears():
    profile = {
        "annual_budget": 12_000,
        "geography": "international",
        "diagnosed_conditions": "no",
        "maternity": True,
        "maximum_maternity_wait": 6,
    }

    assert agents.rank_catalogue_plans(profile, [plan("unknown-overseas", "provider-a", 8_000)]) == []


def test_explanation_uses_one_call_for_the_fixed_ranking(monkeypatch):
    ranked = [
        {"plan_id": f"p{number}", "score": 90 - number, "premium_aed": 8_000 + number, "factors": {}}
        for number in range(1, 6)
    ]
    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            body = {
                "explanations": [
                    {"plan_id": row["plan_id"], "explanation": f"Reason for {row['plan_id']}"}
                    for row in ranked
                ]
            }
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(body)))]
            )

    monkeypatch.setattr(
        agents,
        "settings",
        lambda: SimpleNamespace(groq_api_key="test", groq_model="test-model"),
    )
    monkeypatch.setattr(
        agents,
        "_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )

    explanations = agents.explain_catalogue_ranking(ranked)

    assert len(calls) == 1
    assert [row["plan_id"] for row in explanations] == [row["plan_id"] for row in ranked]


def test_explicit_yes_creates_one_application_per_distinct_provider():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            owner_id, case_id = "member-a", "case-a"
            db.add(Case(id=case_id, owner_id=owner_id, status="open"))
            db.add_all(
                (
                    Provider(id="provider-a", name="Provider A"),
                    Provider(id="provider-b", name="Provider B"),
                )
            )
            quote = Quote(owner_id=owner_id, case_id=case_id, profile_version=1, snapshot={})
            db.add(quote)
            db.flush()
            recommendation = Recommendation(
                owner_id=owner_id,
                case_id=case_id,
                quote_id=quote.id,
                profile_version=1,
                proposed_plan_id="p1",
                status="approved",
            )
            db.add(recommendation)
            db.flush()
            db.add(
                ReviewDecision(
                    owner_id="broker-a",
                    recommendation_id=recommendation.id,
                    action="approve",
                )
            )
            db.flush()
            ranked = [
                {"plan_id": "p1", "provider_id": "provider-a"},
                {"plan_id": "p2", "provider_id": "provider-a"},
                {"plan_id": "p3", "provider_id": "provider-b"},
            ]

            assert create_consented_applications(
                db,
                owner_id=owner_id,
                case_id=case_id,
                profile={"legal_name": "Synthetic Member"},
                ranked=ranked,
                consent="no",
            ) == []
            assert db.scalar(select(func.count()).select_from(MarketplaceApplication)) == 0

            applications = create_consented_applications(
                db,
                owner_id=owner_id,
                case_id=case_id,
                profile={"legal_name": "Synthetic Member", "emirates_id": "encrypted"},
                ranked=ranked,
                consent="yes",
            )
            db.commit()

            assert len(applications) == 2
            rows = db.scalars(select(MarketplaceApplication).order_by(MarketplaceApplication.provider_id)).all()
            assert [(row.provider_id, row.status) for row in rows] == [
                ("provider-a", "sent_to_providers"),
                ("provider-b", "sent_to_providers"),
            ]
            assert rows[0].consent_snapshot["ranked_plan_ids"] == ["p1", "p2"]
            assert "emirates_id" not in rows[0].consent_snapshot["shared_profile"]
    finally:
        engine.dispose()
