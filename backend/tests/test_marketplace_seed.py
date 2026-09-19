from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.marketplace_models import MarketplacePlan, Provider
from app.models import Base

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_marketplace_providers.py"
SPEC = spec_from_file_location("seed_marketplace_providers", SCRIPT)
assert SPEC and SPEC.loader
seed = module_from_spec(SPEC)
SPEC.loader.exec_module(seed)


def test_marketplace_catalogue_seed_is_idempotent_and_preserves_helm_reference_terms():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            first = seed.seed_catalogue(db)
            db.commit()
            second = seed.seed_catalogue(db)
            db.commit()

            assert first == {
                "Helm Direct": 3,
                "Al Noor Takaful": 6,
                "Gulf Shield Insurance": 6,
                "Union Assurance UAE": 7,
                "Pearl Health Partners": 8,
            }
            assert second == first
            assert db.scalar(select(func.count()).select_from(Provider)) == 5
            assert db.scalar(select(func.count()).select_from(MarketplacePlan)) == 30

            helm = db.scalar(select(Provider).where(Provider.name == "Helm Direct"))
            assert helm is not None
            terms = db.scalars(
                select(MarketplacePlan.terms)
                .where(MarketplacePlan.provider_id == helm.id)
                .order_by(MarketplacePlan.plan_code)
            ).all()
            assert terms == sorted(seed.fixture_plans(), key=lambda plan: plan["id"])
    finally:
        engine.dispose()


def test_generated_marketplace_plans_stay_within_the_documented_tier_ranges():
    for provider, plans in seed.planned_catalogue().items():
        if provider == "Helm Direct":
            continue
        for plan in plans:
            ranges = seed.TIER_RANGES[plan["network"]]
            assert ranges["premium"][0] <= plan["annual_premium"] <= ranges["premium"][1]
            assert ranges["deductible"][0] <= plan["deductible"] <= ranges["deductible"][1]
            assert ranges["copay"][0] <= plan["outpatient_copay_pct"] <= ranges["copay"][1]
            assert ranges["annual_limit"][0] <= plan["annual_limit"] <= ranges["annual_limit"][1]
            assert plan["dental_optical"] in {"none", "basic", "full"}
            assert plan["maternity"]["covered"] in {True, False}
            assert plan["chronic_preexisting"]["covered"] in {True, False}
