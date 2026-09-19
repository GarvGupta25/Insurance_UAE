# Marketplace Pivot v2 — Phase 2 report

Phase 2 establishes the provider-owned relational marketplace foundation. It does not alter the
existing JSON-backed Helm Direct comparison catalogue or the current quote flow.

## Data model and security

`supabase/migrations/202609190002_marketplace_pivot.sql` adds these tables:

- `providers` and `provider_users` for provider tenancy;
- `marketplace_plans` for the provider-owned catalogue;
- `marketplace_applications` and `provider_quotations` for the later broker/provider flow;
- `policies_marketplace`, `provider_payments`, and `provider_flags` for the later policy lifecycle.

Every new table has RLS enabled. Members can read only their own marketplace applications,
quotations, policies, payments, and flags; provider users are limited to their mapped provider;
broker and support roles receive full read visibility. Browser clients have no marketplace mutation
grants. The FastAPI backend will own writes in subsequent phases.

The marketplace ORM mapping lives in `backend/app/marketplace_models.py`, deliberately separate
from the stable JSON-domain models so the current deterministic quote engine remains unchanged.

## Seed catalogue

`backend/scripts/seed_marketplace_providers.py` uses the fixed seed `20260919` and writes this exact
catalogue:

| Provider | Plans |
| --- | ---: |
| Helm Direct | 3 |
| Al Noor Takaful | 6 |
| Gulf Shield Insurance | 6 |
| Union Assurance UAE | 7 |
| Pearl Health Partners | 8 |
| Total | 30 |

The three Helm Direct records are exact copies of `backend/data/hackathon_data.json`; the other
27 plans are fictional demonstration data constrained to the required restricted, standard, and
wide tier ranges. Existing plan codes are checked per provider, making a second seed run safe and
allowing a partial seed to be repaired without duplicates.

The default seed also provisions four local-only Supabase Auth provider accounts and rewrites
`SEED_PROVIDER_LOGINS.md`. `--skip-auth` is provided only for catalogue-only verification.

## Verification

Completed locally:

- `uv run python -m py_compile app/marketplace_models.py scripts/seed_marketplace_providers.py`
- `uv run ruff check app/marketplace_models.py scripts/seed_marketplace_providers.py tests/test_marketplace_seed.py`
- `uv run pytest -q tests/test_marketplace_seed.py` — 2 passed

The local Supabase services were stopped at verification time. I did not reset or modify that local
database, so applying the SQL migration and invoking the Auth-provisioning mode remain deliberate
environment setup steps rather than an unverified claim.
