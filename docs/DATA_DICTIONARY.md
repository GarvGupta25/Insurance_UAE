# Phase 1 data dictionary

Every primary record has `id`, `owner_id` and `created_at`. The API derives ownership from the Supabase session and never accepts an owner ID from a browser request.

| Record | Purpose | Important controls |
| --- | --- | --- |
| `profiles` / `profile_versions` | Current reusable facts and append-only versions | Conditional validation; sensitive identity values encrypted when configured; each correction has provenance |
| `shopping_cases`, `messages`, `agent_runs` | One conversation and durable bounded work per shopping journey | Case ownership, 4,000-character messages, leased/retry-bounded jobs; no raw audio in a row |
| `documents` | Extraction hash and reviewed typed values | Raw upload processed in memory and discarded; extraction cannot populate health/funding facts |
| `quotes` | Immutable indicative three-plan snapshot | Profile and catalogue versions make stale quotes visible |
| `applications` | Versioned carrier mapping and confirmation hash | Exact current snapshot and explicit declaration confirmation required |
| `policies` | Frozen selected-plan snapshot | `demo_active` is an in-app sandbox only; imported policies remain unverified |
| `instalments`, `payment_orders`, `receipts` | Simulated or test-mode payment flow | Integer fils, unique schedule position, one receipt per order/instalment, server-computed amount |
| `command_receipts` | Retry/idempotency record | Same key plus different payload returns 409 |
| `audit_events` | Attributed mutation evidence | Backend-only record; no raw health prompts or secrets |

The Plan A/B/C object is retained exactly as supplied in `hackathon_data.json`; implementation fields wrap it rather than renaming its source attributes. Money is stored in fils, displayed in AED and rounded half-up at schedule boundaries.

## Data boundaries

`synthetic_demo`, `indicative`, `demo_active` and `unverified_import` are distinct modes. A current screen must never make a local simulation look like an issued policy, a real payment or insurer-confirmed provider membership.

The initial Phase 1 data model deliberately does not contain the benefit ledger, servicing events, appeal decisions or reassessment output. Those belong to the revised plan's later servicing phase and must use an append-only/replayable model when introduced.
