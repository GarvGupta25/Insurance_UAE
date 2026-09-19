# Helm AI Marketplace Pivot v2 — Phase 0 Reconciliation Audit

**Audit date:** 19 September 2026

**Repository state audited:** working tree on `main` at `ebd3745`, including the existing uncommitted public-assistant/staff-console work

**Scope:** evidence gathering only; no application code was changed

## Executive decisions

1. **Create a separate `provider_quotations` table.** There is no `policy_quotes` ORM class or database table in this repository. The nearest existing object is `quotes`, but it is a member-owned, immutable snapshot of a full three-plan comparison, not one provider-authored offer against one marketplace application. Extending it would mix two different lifecycles and ownership models.
2. **Add both marketplace broker checkpoints to `backend/app/main.py`, reusing `ReviewDecision`.** The current broker recommendation approval is implemented by `review_recommendation()` in that file. The broker worklist and the other broker review flows are there as well.
3. **Reuse `events.py` only for the current single-Uvicorn-process local deployment.** Its queues are in process memory. It can carry new JSON-string event types without new infrastructure when producer and subscribers are in that same API process, but it cannot deliver reliably across multiple Uvicorn workers, restarts, or horizontally scaled instances.
4. **Copy the dependency-wrapper pattern for `require_provider`, but add the provider lookup required by the new role.** Existing authorization verifies the bearer token with Supabase, derives an administrator-controlled role in `current_user()`, and has small FastAPI dependencies that reject the wrong role. No existing dependency resolves a tenant ID from a mapping table, so Phase 5 must add that database lookup rather than claiming it is already a project convention.

## 1. ORM and schema ground truth

### Shared inherited columns

`Recommendation` and `Quote` inherit `Owned` (`backend/app/models.py:20-24`). Therefore each has these columns in addition to its explicit fields:

| Column | ORM type | Nullability/default/constraint |
| --- | --- | --- |
| `id` | `String(36)` / `str` | Primary key; Python default `uid()` |
| `owner_id` | `String(36)` / `str` | Indexed |
| `created_at` | `DateTime(timezone=True)` / `datetime` | Python default `now()` |

The base is literally defined as:

```python
class Owned:
    id = mapped_column(String(36), primary_key=True, default=uid)
    owner_id = mapped_column(String(36), index=True)
    created_at = mapped_column(DateTime(timezone=True), default=now)
```

### `recommendations`

Evidence: `Recommendation` is defined at `backend/app/models.py:156-164`; its migration is in `supabase/migrations/202609130001_servicing.sql`.

| Column | ORM type | Foreign key / constraint / default |
| --- | --- | --- |
| `id` | `String(36)` | Primary key, inherited |
| `owner_id` | `String(36)` | Inherited; ORM index |
| `created_at` | timezone-aware `DateTime` | Inherited |
| `case_id` | inferred `String` / `str` | FK to `shopping_cases.id`; ORM index |
| `quote_id` | inferred `String` / `str` | FK to `quotes.id` |
| `profile_version` | inferred `Integer` / `int` | Required by the typed ORM declaration |
| `proposed_plan_id` | `String(80)` | Required |
| `status` | `String(40)` | Default `pending_review`; ORM index |
| `certainty` | `String(32)` | Default `clear` |
| `summary` | `JSON` / `dict` | Default empty dict |

Database-level details from the migration:

- `id` is the primary key.
- `case_id` references `public.shopping_cases(id)`.
- `quote_id` references `public.quotes(id)`.
- `ix_recommendations_owner_status` indexes `(owner_id, status)`.
- RLS is enabled and all direct access is revoked from `anon` and `authenticated`; mutations are backend-owned.
- There is no database `CHECK` constraint restricting recommendation status or certainty values.

The ORM expresses separate `owner_id`, `case_id`, and `status` indexes, while the committed migration creates a combined owner/status index. That is an existing ORM/migration index-shape difference, not a marketplace change.

### `policy_quotes` does not exist

A repository-wide search of `backend/`, `supabase/`, and `frontend/` finds no `PolicyQuote`, `policy_quotes`, or `__tablename__ = "policy_quotes"`. Therefore there are no columns, foreign keys, or constraints to list. The master-plan assumption that this table already exists is false.

The nearest existing model is `Quote` (`backend/app/models.py:76-80`):

| Column | ORM type | Foreign key / constraint / purpose |
| --- | --- | --- |
| `id` | `String(36)` | Primary key, inherited |
| `owner_id` | `String(36)` | Member owner, inherited |
| `created_at` | timezone-aware `DateTime` | Inherited |
| `case_id` | inferred `String` / `str` | FK to `shopping_cases.id` |
| `profile_version` | inferred `Integer` / `int` | Version used to detect staleness |
| `snapshot` | `JSON` / `dict` | Entire generated comparison snapshot |

`create_quote()` (`backend/app/main.py:535`) stores all compared catalogue items, classification, the recommended plan, ranking version, and catalogue hash in this one snapshot. The table is also protected by the `immutable_history` trigger created in `202609120001_phase_one.sql`. It is not shaped like a mutable provider submission with one provider, one premium, terms, submission status, and submission timestamp.

### Quotation storage decision

**Decision: create `provider_quotations`; do not extend `quotes`.**

Reasons:

- `policy_quotes` is absent, so there is nothing by that name to extend.
- `quotes` represents a member-owned generated comparison; provider quotations represent provider-owned submissions against marketplace applications.
- `quotes.snapshot` contains multiple catalogue alternatives and a catalogue hash. A provider quotation needs a single `provider_id`, submitted premium/terms, quotation status, and `submitted_at`.
- Existing quotes are immutable historical snapshots. Provider quotation statuses must progress through submitted, shortlisted, selected, accepted, declined, or withdrawn.
- Keeping the concepts separate preserves the existing quote, recommendation, application, and policy regression boundary.

Phase 2 should use IDs compatible with the current schema. Existing business IDs and foreign keys are `VARCHAR(36)`, even though they contain UUID text. A new `marketplace_applications.case_id` cannot be PostgreSQL `uuid` while referencing `shopping_cases.id VARCHAR(36)`; either the new FK must be `VARCHAR(36)` or the existing ID strategy must be migrated deliberately.

## 2. Existing broker interaction and review logic

All broker HTTP endpoints and review writes in the three requested files are in `backend/app/main.py`. `backend/app/agents.py` has no broker role check or review-record access. `backend/app/domain.py` has no broker role check or review-record access; it supplies deterministic comparison, application mapping, servicing evaluation, and reassessment calculations called by the API.

### Review-producing or review-gating member functions

| File/function | Evidence | Current behavior |
| --- | --- | --- |
| `backend/app/main.py::prepare_application` | route at line 596; creates `Recommendation` at line 625 | Creates a `pending_review` recommendation and an application with `awaiting_broker_review`. This is the current entry to broker review. |
| `backend/app/main.py::submit_application` | route at line 816 | Requires application status `ready_for_confirmation` and recommendation status `approved` before creating the current sandbox `Policy`. This is the existing server-side post-review gate. |
| `backend/app/main.py::reassess_policy` | route at line 959; creates `PolicyReassessment` at line 987 | Creates a pending policy-fit reassessment for broker review. |
| `backend/app/main.py::submit_appeal` | route at line 1113 | Creates an append-only appeal record that later requires broker review. |

### Broker-facing endpoints

| File/function | Route | One-line description |
| --- | --- | --- |
| `backend/app/main.py::broker_recommendations` | `GET /api/broker/recommendations` | Lists pending recommendations only for members assigned to the authenticated broker. |
| `backend/app/main.py::broker_worklist` | `GET /api/broker/worklist` | Unions pending recommendations, appeals, unresolved insufficient-data decisions, and reassessments into the existing deterministic queue. |
| `backend/app/main.py::broker_case_detail` | `GET /api/broker/cases/{applicant_id}` | Verifies the broker assignment, then reads the member profile, latest quote/recommendation, review history, policy, ledger, and servicing history. |
| `backend/app/main.py::review_recommendation` | `POST /api/broker/recommendations/{recommendation_id}/review` | Locks an assigned recommendation, rejects stale/already-reviewed data, approves or edits the supported plan, writes `ReviewDecision`, and advances the application to `ready_for_confirmation`. |
| `backend/app/main.py::broker_reassessments` | `GET /api/broker/reassessments` | Lists assigned policy reassessments and their review history. |
| `backend/app/main.py::review_reassessment` | `POST /api/broker/reassessments/{reassessment_id}/review` | Records the broker's retained/future plan choice and writes `ReviewDecision`. |
| `backend/app/main.py::broker_appeals` | `GET /api/broker/appeals` | Lists assigned appeals and any appended broker review. |
| `backend/app/main.py::review_appeal` | `POST /api/broker/appeals/{appeal_id}/review` | Upholds or overturns the appealed decision, appends the effective history/replay result, and writes `ReviewDecision`. |

Every broker endpoint above uses `Depends(require_broker)`. Record scoping is then enforced with `BrokerAssignment` joins or the `assigned()` helper in `backend/app/services.py:24-36`; the latter joins the requested owned model to `broker_assignments` and matches `broker_id` to the authenticated broker.

### Phase 3 integration point

The marketplace checkpoints belong in `backend/app/main.py`, alongside `review_recommendation()` and `broker_worklist()`, and must reuse/extend `ReviewDecision`. The model currently distinguishes review targets with nullable foreign keys (`recommendation_id`, `servicing_event_id`, `reassessment_id`) but has no marketplace application/quotation target and no checkpoint/stage column. Phase 2/3 must add an unambiguous marketplace target and checkpoint identity so Checkpoint 2 can never be mistaken for Checkpoint 1.

## 3. Real-time mechanism

Evidence: `backend/app/events.py` was read in full.

### Existing buses and payloads

| Bus | Internal structure | Scope | Payload at broadcast | SSE output |
| --- | --- | --- | --- | --- |
| `escalation_bus` | Global `EventBus` with `list[asyncio.Queue]` | Broadcast to every subscriber registered in this process | Arbitrary `str`; no schema or event-name field is enforced | `event_generator()` yields `{"data": message}` |
| `session_bus` | Global `SessionEventBus` with `dict[session_id, list[asyncio.Queue]]` | Broadcast to subscribers for one `session_id` in this process | Arbitrary `str`; no schema or event-name field is enforced | `session_event_generator()` yields `{"data": message}` |

The current producers serialize JSON themselves before broadcasting. Consequently, a marketplace event can be represented as a JSON string such as `{"type":"provider_notified", ...}` or `{"type":"application_status_changed", ...}`, but `events.py` itself provides no typed envelope, authorization, persistence, replay, bounded queue, or delivery acknowledgement.

### Process boundary and deployment verdict

Both global bus instances and all queues live in Python memory. They cannot cross a process boundary and all subscriptions/events disappear when the API process restarts.

The repository's documented and scripted deployment is currently one Uvicorn API process:

- `README.md:29` runs `uvicorn app.main:app --host 127.0.0.1 --port 8000` with no `--workers` option.
- `scripts/start-prototype.ps1:50` launches the same app with no `--workers` option.
- The separate `python -m app.worker` process handles queued LangGraph work and does not host browser SSE subscriptions.
- No Gunicorn configuration, Uvicorn multi-worker option, Kubernetes replica definition, or horizontal-scaling configuration was found.

**Answer for the current repository: YES, with a strict single-process limitation.** New marketplace event types can reuse these buses as-is in the configured local demo when their producer runs in the one API process. **Answer for multi-worker or horizontally scaled deployment: NO.** Each worker would have a different subscriber list, so events would reach only clients connected to the producing process. Phase 7 must use polling or introduce a shared transport before claiming reliable cross-process live delivery.

## 4. Authentication and role-check pattern

Evidence: `backend/app/auth.py` was read in full.

### Authentication source

`current_user()` does not trust browser-decoded claims. It sends the bearer token to Supabase Auth's `/auth/v1/user` endpoint with the configured anonymous key. It takes `id`, `email`, and `app_metadata.helm_role` from the verified response. Supabase administrator-controlled `app_metadata`, rather than user-editable metadata, is therefore the intended role source.

Current `User.role` values are typed as `member | broker | support_agent`.

### Existing role dependencies

| Dependency | Exact pattern |
| --- | --- |
| `current_user` | Verifies the bearer token remotely with Supabase, maps `app_metadata.helm_role == "support_agent"` to support, `== "broker"` to broker, and everything else to member. |
| `require_broker` | Receives `User = Depends(current_user)`; checks `user.role != "broker"`; raises HTTP 403; otherwise returns the same `User`. |
| `require_support_agent` | Receives `User = Depends(current_user)`; checks `user.role != "support_agent"`; raises HTTP 403; otherwise returns the same `User`. |

There is **no `require_member` dependency**. Ordinary member routes depend directly on `current_user`; database access helpers then enforce `owner_id == user.id`. There is also no existing role dependency that consults a role roster table.

The current working tree contains a special-case override that assigns `support_agent` when the verified email equals `staff@helm.ai`. That bypasses the otherwise stated administrator-controlled metadata rule. It is pre-existing Phase 0 input, not introduced by this audit, and should not be copied for providers.

### Required Phase 5 provider pattern

Phase 5 should:

1. Extend the typed role union and `current_user()` mapping with `provider`, sourced from verified `app_metadata.helm_role` exactly like broker/support roles.
2. Define `require_provider` as a FastAPI dependency on `current_user()` and reject non-provider roles with HTTP 403, matching `require_broker`/`require_support_agent`.
3. Inject a database session into `require_provider`, query `provider_users` by the authenticated `user.id`, and fail closed if there is no active mapping.
4. Return an immutable provider context containing the verified user plus the database-derived `provider_id`. Provider endpoints must never accept `provider_id` from a path, query, or request body as authority.

This combines the repository's real role-check pattern with the new tenant lookup demanded by provider isolation. Describing the lookup as an existing pattern would be inaccurate.

## 5. Contradictions and required corrections before later phases

### Blocking schema contradictions

1. **No `policy_quotes`:** use a new `provider_quotations` table.
2. **No database plan/catalogue table:** `backend/app/domain.py::plans()` loads `backend/data/hackathon_data.json`; there is no `Plan` ORM class or `plans` table. Phase 2 cannot `ALTER TABLE <existing plan/catalogue table> ADD provider_id`. It must first make an explicit architecture decision: introduce a database catalogue and preserve the JSON fixture as the immutable Helm Direct source/seed, or intentionally expand the JSON catalogue and use a separate provider/plan persistence model. A relational marketplace with provider ownership and seeded provider plans strongly favors a new `plans` table plus a compatibility adapter in `domain.py`, but Phase 8 currently declares `domain.py` out of scope. Those two instructions must be reconciled before Phase 2.
3. **ID type mismatch:** current business-table IDs are `VARCHAR(36)`. The Phase 2 sample's `marketplace_applications.case_id uuid` cannot directly reference `shopping_cases.id VARCHAR(36)`.
4. **Application/provider relationship missing from the sample schema:** Phase 4 requires one marketplace application row per distinct provider, and Phase 2's RLS text requires provider scoping, but the sample `marketplace_applications` table has no `provider_id` (or join table) and no member/owner field. It cannot implement either requirement as written. Add `provider_id` and `owner_id`, or model a parent marketplace case plus a provider-recipient join table.
5. **Checkpoint identity missing:** current `ReviewDecision` has no marketplace target or checkpoint number. Add explicit structure for two distinct approvals.

### Code and runtime contradictions

1. The current frontend dependencies are React `19.1.0`, not React 18.
2. Tailwind 4 is installed and loaded by `frontend/vite.config.ts`, although the established member/broker design system primarily uses standard classes from `frontend/src/styles.css`. The existing staff console uses Tailwind utility classes.
3. Broker logic is not in `agents.py` or `domain.py`; it is in `backend/app/main.py`.
4. `events.py` is suitable only for the present single-process API deployment, not a generally reliable cross-process notification system.
5. `auth.py` has `require_broker` and `require_support_agent`, but no `require_member`.
6. The current LangGraph in `backend/app/agents.py` is a single `interpret` node, confirming Phase 1 is a real state-machine rebuild rather than a small extension.
7. The existing policy-binding flow has one broker approval followed by member `submit_application()` creating a `Policy`. The target marketplace flow requires provider acceptance, a separate second broker approval, and provider-controlled Start Policy, so Phase 3/5/6 must replace that marketplace path without weakening the existing sandbox path unintentionally.

## Phase 0 verification checklist

- [x] `recommendations` documented at column level.
- [x] Absence of `policy_quotes` proven; nearest `quotes` table documented.
- [x] Separate `provider_quotations` table recommended with schema-based reasoning.
- [x] Broker endpoints and review-producing/gating functions located precisely.
- [x] `events.py` payloads, process scope, and current deployment model documented.
- [x] Existing auth dependencies and the exact provider adaptation documented.
- [x] Master-plan contradictions flagged rather than silently absorbed.

## Exit decision

Phase 0 is complete. Phase 1 can start against `backend/app/agents.py`, but Phase 2 must use the corrections in Section 5 rather than copying its illustrative SQL literally. No application code should be written until the catalogue persistence choice, provider/application relationship, ID types, and two-checkpoint review identity are reflected in the Phase 2/3 implementation design.
