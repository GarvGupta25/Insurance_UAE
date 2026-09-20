"""Seed the reproducible fictional Marketplace Pivot v2 provider catalogue.

Run after applying `202609190002_marketplace_pivot.sql`:
    uv run python scripts/seed_marketplace_providers.py

Use --skip-auth only for catalogue-only local verification. The default provisions the four
fictional provider logins through local Supabase Auth and writes SEED_PROVIDER_LOGINS.md.
"""

import argparse
import json
import random
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import engine
from app.marketplace_models import (
    MarketplaceApplication,
    MarketplacePlan,
    Provider,
    ProviderQuotation,
)
from app.models import Case

SEED = 20260919
ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "backend" / "data" / "hackathon_data.json"

PROVIDER_SPECS = (
    {
        "name": "Helm Direct",
        "slug": "helm-direct",
        "count": 3,
        "weights": None,
        "display_name": None,
    },
    {
        "name": "Al Noor Takaful",
        "slug": "al-noor-takaful",
        "count": 6,
        "weights": {"restricted": 0.7, "standard": 0.3, "wide": 0.0},
        "display_name": "Al Noor Marketplace Team",
    },
    {
        "name": "Gulf Shield Insurance",
        "slug": "gulf-shield-insurance",
        "count": 6,
        "weights": {"restricted": 0.0, "standard": 0.25, "wide": 0.75},
        "display_name": "Gulf Shield Marketplace Team",
    },
    {
        "name": "Union Assurance UAE",
        "slug": "union-assurance-uae",
        "count": 7,
        "weights": {"restricted": 0.1, "standard": 0.8, "wide": 0.1},
        "display_name": "Union Assurance Marketplace Team",
    },
    {
        "name": "Pearl Health Partners",
        "slug": "pearl-health-partners",
        "count": 8,
        "weights": {"restricted": 0.2, "standard": 0.55, "wide": 0.25},
        "display_name": "Pearl Health Marketplace Team",
    },
)

TIER_RANGES = {
    "restricted": {
        "premium": (3000, 6500),
        "deductible": (1000, 2000),
        "copay": (25, 35),
        "annual_limit": (100000, 200000),
    },
    "standard": {
        "premium": (6500, 13000),
        "deductible": (300, 800),
        "copay": (15, 25),
        "annual_limit": (300000, 600000),
    },
    "wide": {
        "premium": (13000, 26000),
        "deductible": (0, 500),
        "copay": (5, 15),
        "annual_limit": (800000, 2000000),
    },
}


def fixture_plans() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8-sig"))["plans"]


def provider_login(spec: dict) -> tuple[str, str]:
    email = f"provider@{spec['slug']}.helm-demo.test"
    password = "HelmDemo2026!" + "".join(part.title() for part in spec["slug"].split("-"))
    return email, password


def _tier(rng: random.Random, weights: dict[str, float]) -> str:
    names = tuple(weights)
    return rng.choices(names, weights=tuple(weights[name] for name in names), k=1)[0]


def _generated_plan(rng: random.Random, spec: dict, position: int) -> dict:
    network = _tier(rng, spec["weights"])
    ranges = TIER_RANGES[network]
    annual_limit = rng.randint(*ranges["annual_limit"])
    maternity_covered = rng.random() < 2 / 3
    chronic_covered = rng.random() < 2 / 3
    plan_code = f"{spec['slug'].replace('-', '_')}_{position}"
    return {
        "id": plan_code,
        "name": f"{spec['name']} {network.title()} {position}",
        "annual_premium": rng.randint(*ranges["premium"]),
        "deductible": rng.randint(*ranges["deductible"]),
        "network": network,
        "network_note": f"Fictional {network} demonstration network for {spec['name']}.",
        "outpatient_copay_pct": rng.randint(*ranges["copay"]),
        "maternity": (
            {
                "covered": True,
                "waiting_period_months": rng.randint(0, 12),
                "limit": int(annual_limit * rng.uniform(0.15, 0.20)),
            }
            if maternity_covered
            else {"covered": False}
        ),
        "chronic_preexisting": (
            {"covered": True, "waiting_period_months": rng.randint(0, 9)}
            if chronic_covered
            else {"covered": False}
        ),
        "annual_limit": annual_limit,
        "dental_optical": rng.choice(("none", "basic", "full")),
    }


def planned_catalogue() -> dict[str, list[dict]]:
    """Build every plan before checking the database so partial reruns remain deterministic."""
    rng = random.Random(SEED)
    plans = {"Helm Direct": [deepcopy(plan) for plan in fixture_plans()]}
    for spec in PROVIDER_SPECS[1:]:
        plans[spec["name"]] = [_generated_plan(rng, spec, position) for position in range(1, spec["count"] + 1)]
    return plans


def get_or_create_provider(db: Session, name: str) -> Provider:
    provider = db.scalar(select(Provider).where(Provider.name == name))
    if provider:
        return provider
    provider = Provider(name=name, is_seed_demo=True)
    db.add(provider)
    db.flush()
    return provider


def seed_catalogue(db: Session) -> dict[str, int]:
    """Idempotently seed providers and their complete plan sets; caller owns the transaction."""
    catalogue = planned_catalogue()
    counts: dict[str, int] = {}
    for spec in PROVIDER_SPECS:
        provider = get_or_create_provider(db, spec["name"])
        existing_codes = set(
            db.scalars(
                select(MarketplacePlan.plan_code).where(MarketplacePlan.provider_id == provider.id)
            ).all()
        )
        for plan in catalogue[spec["name"]]:
            if plan["id"] not in existing_codes:
                db.add(
                    MarketplacePlan(
                        provider_id=provider.id,
                        plan_code=plan["id"],
                        name=plan["name"],
                        terms=plan,
                        is_helm_direct_reference=spec["name"] == "Helm Direct",
                    )
                )
            db.flush()
        counts[spec["name"]] = db.scalar(
            select(func.count()).select_from(MarketplacePlan).where(MarketplacePlan.provider_id == provider.id)
        )
    return counts


def seed_performance_examples(db: Session) -> None:
    """Seed reproducible quotation timing evidence for the broker performance view."""
    case = db.get(Case, "perf-demo-case")
    if case is None:
        db.add(Case(id="perf-demo-case", owner_id="perf-demo-member", status="open"))
        db.flush()
    sent_at = datetime(2026, 9, 19, 8, tzinfo=timezone.utc)
    turnaround_hours = {
        "Pearl Health Partners": 2,
        "Al Noor Takaful": 12,
        "Gulf Shield Insurance": 18,
        "Union Assurance UAE": 24,
    }
    for position, (provider_name, hours) in enumerate(turnaround_hours.items(), 1):
        provider = db.scalar(select(Provider).where(Provider.name == provider_name))
        plan = db.scalar(
            select(MarketplacePlan)
            .where(MarketplacePlan.provider_id == provider.id)
            .order_by(MarketplacePlan.plan_code)
        )
        application_id, quotation_id = f"perf-app-{position}", f"perf-quote-{position}"
        if db.get(MarketplaceApplication, application_id) is None:
            db.add(
                MarketplaceApplication(
                    id=application_id,
                    owner_id="perf-demo-member",
                    case_id="perf-demo-case",
                    provider_id=provider.id,
                    status="customer_selected" if provider_name == "Pearl Health Partners" else "declined",
                    consent_snapshot={"seed_demo": True},
                    created_at=sent_at,
                )
            )
            db.flush()
        if db.get(ProviderQuotation, quotation_id) is None:
            db.add(
                ProviderQuotation(
                    id=quotation_id,
                    application_id=application_id,
                    provider_id=provider.id,
                    marketplace_plan_id=plan.id,
                    plan_terms=plan.terms,
                    premium=plan.terms["annual_premium"],
                    status="selected" if provider_name == "Pearl Health Partners" else "declined",
                    submitted_at=sent_at + timedelta(hours=hours),
                )
            )


def provision_provider_accounts(db: Session) -> list[tuple[str, str]]:
    """Create four local Supabase Auth provider accounts and their provider_users mappings."""
    cfg = settings()
    if not cfg.supabase_anon_key:
        raise SystemExit("Local Supabase configuration is missing; cannot provision provider demo accounts.")

    credentials = []
    with httpx.Client(timeout=15) as client:
        for spec in PROVIDER_SPECS[1:]:
            email, password = provider_login(spec)
            account_id = db.execute(
                text("SELECT id::text FROM auth.users WHERE email = :email"), {"email": email}
            ).scalar_one_or_none()
            if not account_id:
                response = client.post(
                    cfg.supabase_url.rstrip("/") + "/auth/v1/signup",
                    headers={"apikey": cfg.supabase_anon_key, "Content-Type": "application/json"},
                    json={"email": email, "password": password},
                )
                response.raise_for_status()
                account_id = response.json()["user"]["id"]

            db.execute(
                text(
                    "UPDATE auth.users SET encrypted_password = crypt(:password, gen_salt('bf')), "
                    "email_confirmed_at = COALESCE(email_confirmed_at, now()), "
                    "raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) "
                    "|| '{\"helm_role\":\"provider\"}'::jsonb, updated_at = now() "
                    "WHERE id = CAST(:id AS uuid)"
                ),
                {"id": account_id, "password": password},
            )
            provider = db.scalar(select(Provider).where(Provider.name == spec["name"]))
            assert provider is not None
            db.execute(
                text(
                    "INSERT INTO public.provider_users (user_id, provider_id, display_name) "
                    "VALUES (CAST(:user_id AS uuid), :provider_id, :display_name) "
                    "ON CONFLICT (user_id) DO UPDATE SET provider_id = EXCLUDED.provider_id, "
                    "display_name = EXCLUDED.display_name"
                ),
                {
                    "user_id": account_id,
                    "provider_id": provider.id,
                    "display_name": spec["display_name"],
                },
            )
            credentials.append((email, password))
    return credentials


def write_credentials(credentials: list[tuple[str, str]]) -> None:
    lines = [
        "# DEMO/TEST CREDENTIALS - fictional providers, not real accounts",
        "",
        "These local-only credentials are reproducible seed data. They must never be used for real insurance,",
        "payment, customer, or provider systems.",
        "",
        "| Provider login | Temporary password |",
        "| --- | --- |",
    ]
    lines.extend(f"| `{email}` | `{password}` |" for email, password in credentials)
    (ROOT / "SEED_PROVIDER_LOGINS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-auth",
        action="store_true",
        help="Seed only providers and plans; intended for catalogue-only verification.",
    )
    args = parser.parse_args()

    with Session(engine()) as db:
        counts = seed_catalogue(db)
        seed_performance_examples(db)
        credentials = [provider_login(spec) for spec in PROVIDER_SPECS[1:]]
        if not args.skip_auth:
            credentials = provision_provider_accounts(db)
        db.commit()

    write_credentials(credentials)
    print("Marketplace provider seed complete.")
    for provider, count in counts.items():
        print(f"{provider}: {count} plans")
    if args.skip_auth:
        print("Auth provisioning was skipped.")


if __name__ == "__main__":
    main()
