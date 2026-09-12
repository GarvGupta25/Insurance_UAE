# Helm AI

Helm AI is a local, synthetic demonstration of a UAE individual health-insurance journey. It captures a reusable profile through conversation or structured editing, compares three fictional plans, prepares a sandbox application, creates a demonstration policy and records sandbox payment receipts.

It never presents a fictional plan as real cover. A quote is indicative; a sandbox policy is not insurer-issued; a local simulator or Razorpay test receipt never activates real insurance.

## Phase 1 included

- Supabase email/password sign-up, verification, recovery and server-side ownership checks.
- Three-stage conversational intake plus a full editable profile.
- Optional identity extraction from JPG/PNG/PDF, with reviewed provisional fields; raw documents are not retained.
- Versioned fictional catalogue, deterministic matching, a downloadable PDF quotation and visible waiting-period/network tradeoffs.
- Two application mappings, snapshot hashing, explicit declaration confirmation and an in-app carrier sandbox.
- Portfolio, frozen policy terms, a monthly/annual simulated schedule, idempotent local payments and an optional Razorpay test adapter.
- Fictional provider list/map, source-labelled updates, keyboard-accessible responsive screens and shared voice components.
- Voice capture is short push-to-talk, with an editable transcript before it becomes a message. Optional read-aloud uses the browser voice. Audio is only sent to Groq when `GROQ_API_KEY` is configured and is not stored by Helm.

## Run locally

Requirements: Node 22+, Python 3.12, `uv`, Docker Desktop and the local Supabase CLI dependency installed by this repository.

1. At the repository root run `npm install`, then `npx supabase start --ignore-health-check` and `npx supabase db reset --no-seed`. The ignore-health-check option is documented here because the current Windows CLI can report a profile-file warning while all required local services start.
2. Run `npx supabase status -o json 2>$null | uv run python scripts/configure_local.py` from `backend/` once. It writes ignored local `.env` files without printing keys.
3. Run `uv sync --python 3.12` in `backend/`, then start the API with `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000` and the worker with `uv run python -m app.worker`.
4. Run `npm install` in `frontend/`, then `npm run dev -- --port 5173`. Open `http://127.0.0.1:5173`.

For the Groq chat/transcription integration, put `GROQ_API_KEY` in `backend/.env`. The app accurately degrades to manual profile editing when it is absent. To test Razorpay, set `PAYMENT_PROVIDER=razorpay` and use only `rzp_test_` credentials. The default is the local simulator.

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
```

The last backend command uses a new synthetic local Supabase account and checks the entire authenticated flow. It does not use a real carrier, payment or Groq credential.

## Project map

- `frontend/` — React/Vite experience and shared voice controls.
- `backend/app/` — FastAPI API, ownership enforcement, LangGraph worker, deterministic comparison, PDF, OCR and payment adapters.
- `supabase/migrations/` — database schema, RLS and immutable-record controls.
- `backend/data/hackathon_data.json` — unchanged supplied fictional plan/profile fixture source.
- `docs/` — delivery boundary, schema and operational decisions.

Read [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md), [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) and [docs/DECISIONS.md](docs/DECISIONS.md) before extending the product.
