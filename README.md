# Helm AI

Helm AI is a local, synthetic demonstration of a UAE individual health-insurance journey. It captures a reusable profile through conversation or structured editing, compares three fictional plans, prepares a sandbox application, creates a demonstration policy and records sandbox payment receipts.

It never presents a fictional plan as real cover. A quote is indicative; a sandbox policy is not insurer-issued; a local simulator or Razorpay test receipt never activates real insurance.

## Phase 1 included

- Supabase email/password sign-up, verification, recovery and server-side ownership checks.
- Three-stage conversational intake plus a full editable profile.
- Optional identity extraction from JPG/PNG/PDF, with reviewed provisional fields; raw documents are not retained.
- Versioned fictional catalogue, deterministic matching, a downloadable PDF quotation and visible waiting-period/network tradeoffs.
- Guided chat that can finish a reviewed profile and generate the indicative quote; a saved, drag-to-explore financial planner uses the same fictional terms for premium, contribution and outpatient-cost illustrations. See [docs/AGENTIC_SHOPPING_FINANCE.md](docs/AGENTIC_SHOPPING_FINANCE.md).
- Two application mappings, snapshot hashing, explicit declaration confirmation and an in-app carrier sandbox.
- Portfolio, frozen policy terms, a monthly/annual simulated schedule, idempotent local payments and an optional Razorpay test adapter.
- Broker review before a prepared application can be confirmed, including the documented fit brief and supported-plan edits.
- Separate broker Auth accounts and administrator-managed case assignments; see [docs/BROKER_SETUP.md](docs/BROKER_SETUP.md).
- Deterministic pre-authorisation, claim and reimbursement servicing with an append-only history and rebuildable benefit ledger.
- Member appeal submission, broker uphold/overturn decisions, corrected effective revisions and history-aware policy-fit reassessments.
- Fictional provider list/map, source-labelled updates, keyboard-accessible responsive screens and shared voice components.
- An approved official-page registry and bounded source refresh for independent research; those unreviewed pages never set sandbox premiums or policy terms.
- Voice capture is short push-to-talk, with an editable transcript before it becomes a message. Optional read-aloud uses the browser voice. Audio is only sent to Groq when `GROQ_API_KEY` is configured and is not stored by Helm.

## Run locally

For a quick, interactive branch preview without Docker or Supabase, follow [docs/LOCAL_PREVIEW.md](docs/LOCAL_PREVIEW.md). It runs against an ignored SQLite demo database with synthetic member and broker roles. The setup below is for the full Supabase-backed development environment.

Requirements: Node 22+, Python 3.12, `uv`, Docker Desktop and the local Supabase CLI dependency installed by this repository.

1. At the repository root run `npm install`, then `npx supabase start --ignore-health-check` and `npx supabase db reset --no-seed`. The ignore-health-check option is documented here because the current Windows CLI can report a profile-file warning while all required local services start.
2. Run `npx supabase status -o json 2>$null | uv run python scripts/configure_local.py` from `backend/` once. It writes ignored local `.env` files without printing keys.
3. Run `uv sync --python 3.12` in `backend/`, then start the API with `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` and the worker with `uv run python -m app.worker`.
4. Run `npm install` in `frontend/`, then `npm run dev -- --port 5173`. Open `http://127.0.0.1:5173`.

For public-source evidence, run `uv run python -m scripts.refresh_sources` from `backend/` after the migrations. Failed source fetches keep previous evidence; they do not invent terms. See [docs/SOURCE_REGISTRY.md](docs/SOURCE_REGISTRY.md).

For the Groq chat/transcription integration, put `GROQ_API_KEY` in `backend/.env`. The app accurately degrades to manual profile editing when it is absent. To test Razorpay, set `PAYMENT_PROVIDER=razorpay` and use only `rzp_test_` credentials. The default is the local simulator.

Image OCR additionally requires a local Tesseract executable; set `TESSERACT_CMD` in `backend/.env` to its full path on Windows if it is not on `PATH`. Text-based PDFs can be extracted without Tesseract. An unreadable image or unavailable OCR keeps manual entry available. `backend/.env.example` documents every optional variable. For Razorpay test checkout, configure `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET`, and point the test webhook to `/api/webhooks/razorpay`; the adapter refuses live keys. Verify your test account supports the proposed currency before selecting Razorpay mode.

## Verification

From `backend/`:

```powershell
uv run ruff check app scripts tests
uv run pytest -q
uv run python scripts/live_smoke.py
```

From `frontend/`:

```powershell
npm run check
npm run build
npx playwright install chromium
npm run test:e2e
```

The last backend command creates separate synthetic member and broker accounts, assigns the broker through the local administrator database connection, and checks the authenticated quote → approval → policy → claim → sandbox receipt flow. It requires the local Supabase stack, API and worker to be running. It does not use a real carrier, payment or Groq credential.

## Local data backup

With Supabase running, create a public-schema backup with `npx supabase db dump --local -f schema-backup.sql` and a public-data backup with `npx supabase db dump --local --data-only -f data-backup.sql`. Store both outside Git in a protected location because profiles and messages may contain sensitive data. To restore an existing local instance after migrations are applied, load the data backup with `psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -f data-backup.sql`. This CLI dump excludes Supabase-managed Auth data, so it is **not** a complete account recovery backup; keep a separate platform-level database backup for that purpose and test recovery in an isolated instance. Raw uploaded documents and voice audio are not retained.

## Project map

- `frontend/` — React/Vite experience and shared voice controls.
- `backend/app/` — FastAPI API, ownership enforcement, LangGraph worker, deterministic comparison, PDF, OCR and payment adapters.
- `supabase/migrations/` — database schema, RLS and immutable-record controls.
- `backend/data/hackathon_data.json` — unchanged supplied fictional plan/profile fixture source.
- `docs/` — delivery boundary, schema and operational decisions.

Read [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md), [docs/PHASE_1_4_ACCEPTANCE.md](docs/PHASE_1_4_ACCEPTANCE.md), [docs/PHASE_ONE_WALKTHROUGH.md](docs/PHASE_ONE_WALKTHROUGH.md), [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md), [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) and [docs/DECISIONS.md](docs/DECISIONS.md) before extending the product.
