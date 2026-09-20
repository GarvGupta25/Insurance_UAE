# Claim Management Phase 0 Audit

Phase 0 is documentation and boundary lock only. No claim-management schema, agent, endpoint, or
UI has been added. All committed-code line references below are against baseline commit `bc9abe6`
(the current `origin/main` when this audit was finalized).

## 1. Existing servicing operations

The repository does **not** contain four separate Python adjudication functions. Pre-authorization,
claim adjudication, and reimbursement share one validated request model, one deterministic
evaluator, and one persistence function. Appeal submission and review are separate API operations,
but an overturn still gets its figures from the same deterministic evaluator and then rebuilds the
same ledger.

### Exact signatures

The two public financial-servicing handlers are in `backend/app/main.py:1036-1092`:

```python
def preview_servicing(
    policy_id: str,
    body: ServicingRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
)

def submit_servicing(
    policy_id: str,
    body: ServicingRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
)
```

`ServicingRequest` is defined at `backend/app/contracts.py:221-246`. Its `kind` is exactly
`Literal["claim", "preauth", "reimbursement"]`; its validator requires `billed_amount` for a
claim, `estimated_amount` for a pre-authorization, and `amount_paid_by_member` for a reimbursement.
Thus these are the exact current operation mappings:

| Operation | Entry point | Authoritative path |
| --- | --- | --- |
| Pre-authorization | `submit_servicing(..., body.kind="preauth", ...)` | `record_financial_event(db, policy, operation)`; it calls `evaluate_servicing(...)` and records a non-ledger-consuming forecast. |
| Claim adjudication | `submit_servicing(..., body.kind="claim", ...)` | The same `record_financial_event(...)`; a covered result participates in ledger replay. |
| Reimbursement | `submit_servicing(..., body.kind="reimbursement", ...)` | The same `record_financial_event(...)`; a covered result participates in ledger replay. |
| Read-only preview for any of the above | `preview_servicing(...)` | Calls `evaluate_servicing(...)` directly and writes nothing. |

The internal servicing signatures, read in full at `backend/app/servicing.py:8-153`, are:

```python
def _projection(db, policy)
def _next_sequence(db, policy_id)
def present_event(record)
def rebuild_projection(db, policy)
def record_financial_event(db, policy, request)
```

The pure calculation entry point is `evaluate_servicing(plan, operation, ledger=None)` in
`backend/app/domain.py:309-399`. It alone validates the financial kind and computes `outcome`,
`reason_code`, plan/member shares, the calculation trace, and before/after ledgers. The persistence
path calls it at `backend/app/servicing.py:125`; replay calls it at
`backend/app/servicing.py:69`.

### Appeal signatures and flow

Appeals are defined by `AppealRequest` and `BrokerAppealReview` at
`backend/app/contracts.py:263-298`. Their API signatures are at
`backend/app/main.py:1099-1106` and `backend/app/main.py:1185-1192`:

```python
def submit_appeal(
    policy_id: str,
    body: AppealRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
)

def review_appeal(
    appeal_id: str,
    body: BrokerAppealReview,
    user: User = Depends(require_broker),
    db: Session = Depends(session),
    idempotency_key: str = Header(),
)
```

`submit_appeal` accepts only a currently denied `claim` or `reimbursement`, appending a record with
`record_type="appeal"` and no financial decision fields (`backend/app/main.py:1109-1155`). On
`uphold`, review appends an `appeal_review` record and retains the existing effective decision. On
`overturn`, it applies only the reviewed correction to the original payload, calls the existing
`evaluate_servicing(...)`, appends a `revision`, and calls `rebuild_projection(...)`
(`backend/app/main.py:1195-1277`). The broker never supplies a payable figure.

## 2. Append-only event log

### Exact persisted shape

`ServicingEvent` is defined at `backend/app/models.py:184-203`; database nullability and indexes are
authoritative in `supabase/migrations/202609130001_servicing.sql:35-59`.

| Field | Required | Shape / role |
| --- | --- | --- |
| `id` | Yes | `VARCHAR(36)` primary key; inherited ORM default generates UUID text. |
| `owner_id` | Yes | `VARCHAR(36)` member owner; inherited and indexed by the ORM. |
| `policy_id` | Yes | `VARCHAR(36)` FK to `policies.id`; indexed. |
| `root_id` | Yes | `VARCHAR(80)` stable logical event reference; indexed. |
| `record_type` | Yes | `VARCHAR(24)`; current code writes `decision`, `revision`, `appeal`, or `appeal_review`. No DB check constraint enumerates these values. |
| `kind` | Yes | `VARCHAR(24)`; financial kinds are `preauth`, `claim`, `reimbursement`; appeal records use `appeal`. |
| `effective_month` | No | Integer policy month used to order effective financial events. |
| `sequence` | Yes | Integer append order within a policy. |
| `payload` | Yes | JSONB immutable source request or review payload. |
| `outcome` | No | `VARCHAR(32)`; null on non-decision appeal records. |
| `reason_code` | No | `VARCHAR(40)`; null on non-decision appeal records. |
| `plan_pays_fils` | No | Integer fils; null where no financial decision exists or data is insufficient. |
| `member_pays_fils` | No | Integer fils; same rule as above. |
| `calculation` | Yes | JSONB list, default `[]`; deterministic calculation trace. |
| `ledger_before` | No | JSONB projection before the decision. |
| `ledger_after` | No | JSONB projection after the decision. |
| `supersedes_id` | No | Self-FK connecting an appeal/revision/review to prior history. |
| `reviewer_action` | No | Broker/replay attribution such as `uphold`, `overturn`, or `automatic_replay`. |
| `created_at` | Yes | Time-zone-aware append timestamp inherited from `Owned`. |

There is a partial unique index allowing only one original `decision` per `(policy_id, root_id)` at
`202609130001_servicing.sql:57`. More importantly, the database trigger at lines 72-76 rejects every
`UPDATE` or `DELETE` on `servicing_events`; corrections are new rows, never mutations.

`present_event(record)` at `backend/app/servicing.py:23-40` is the exact serialized API view. It
renames `root_id` to `event_id`, `effective_month` to `policy_month`, and `created_at` to
`recorded_at`, while returning every decision, ledger, supersession, and reviewer field.

## 3. Derived ledger projection

The initial ledger is defined only by `empty_ledger()` at `backend/app/domain.py:256-262`:

```json
{
  "deductible_met_fils": 0,
  "annual_paid_fils": 0,
  "maternity_paid_fils": 0,
  "financial_event_ids": []
}
```

`LedgerProjection` (`backend/app/models.py:206-212`) is explicitly disposable and derived. Its
persisted fields are inherited `id`, `owner_id`, and `created_at`, plus unique `policy_id`, integer
`through_sequence` (default `0`), and JSON `ledger`.

`rebuild_projection(db, policy)` at `backend/app/servicing.py:43-103`:

1. reads only `decision` and `revision` records for the policy in sequence order;
2. keeps the latest appended row for each `root_id` while retaining the original sequence for stable
   ordering;
3. sorts effective roots by policy month, then original sequence;
4. skips pre-authorizations because they are forecasts;
5. calls `evaluate_servicing(...)` for every other effective root;
6. appends an `automatic_replay` revision if a recomputed decision changed; and
7. advances balances only when the deterministic outcome is exactly `covered`, then stores the
   resulting ledger and `through_sequence`.

The event log is therefore authoritative; `benefit_ledger_projections` is a rebuildable cache, not a
second adjudication record.

## 4. Broker worklist and reviewer approvals

The main aggregation is `GET /api/broker/worklist` in
`backend/app/main.py::broker_worklist` (`backend/app/main.py:669-710`). It currently unions:

- pending recommendations;
- unreviewed servicing appeals;
- latest unresolved servicing decisions with `reason_code="insufficient_data"`;
- pending policy reassessments; and
- Phase 3 marketplace checkpoints/provider flags from
  `backend/app/marketplace_broker.py::marketplace_worklist_items` (lines 98-143).

It deterministically sorts by descending age, urgency class, descending amount, then ID. Claim Phase
4 requires a dedicated `/broker/claims` page, so later claim-intake detail must not be flattened into
these generic rows. A minimal optional count/link can reuse this aggregator, but the master plan's
dedicated page remains the source of claim-review context.

Reviewer attribution uses `ReviewDecision` (`backend/app/models.py:167-181`) plus append-only domain
history and `Audit` entries:

- recommendation approval: `review_recommendation` at `backend/app/main.py:737-799`;
- reassessment approval: `review_reassessment` at `backend/app/main.py:1009-1033`;
- appeal review: `review_appeal` at `backend/app/main.py:1185-1277`, which appends both an
  `appeal_review` `ServicingEvent` and a `ReviewDecision` linked through `servicing_event_id`; and
- marketplace checkpoints: `backend/app/marketplace_broker.py`, including the reusable Phase 3 send
  and binding guards.

All broker paths depend on `require_broker` and scope member records through `BrokerAssignment` or
`assigned(...)`. Later claim review must reuse those two controls and must append reviewer actions;
it must not update a prior `ServicingEvent`.

## 5. Real-time event buses

The committed baseline has **no `backend/app/events.py`**. The user's source checkout contains an
untracked implementation, but it does not exist in commit `bc9abe6` and Phase 0 does not absorb that
unrelated work. Later claim phases may use it as a structural template only after it is deliberately
committed and verified.

Current worktree shape (`backend/app/events.py:5-82`):

| Bus | Structure | Delivery scope |
| --- | --- | --- |
| `escalation_bus` | One global `EventBus` containing a list of `asyncio.Queue` subscribers. | Broadcasts a string to every subscriber in this Python process. |
| `session_bus` | One global `SessionEventBus` mapping `session_id` to queue lists. | Broadcasts a string only to that session's subscribers in this Python process. |

`event_generator` and `session_event_generator` expose these queues as SSE data and poll disconnect
state with a one-second timeout. There is no persistence, replay, bounded queue, delivery receipt,
authentication envelope, or shared transport. The configured launcher starts one Uvicorn API
process (`README.md:29`, `scripts/start-prototype.ps1:50`) and a separate LangGraph worker.

**Cross-process verdict:** the buses work only when producer and subscriber are in the same API
process. They do not cross the worker boundary, multiple Uvicorn workers, replicas, or restarts. A
later claim phase must use polling or a shared transport before describing claim notifications as
reliable cross-process real time.

## 6. Hard boundary for every later phase

> No function added in this task may compute or return an outcome, plan_pays, member_pays, or reason_code value. Every one of those values comes only from calling the existing servicing.py functions unchanged. Any new agent code that finds itself computing a number instead of calling servicing.py is a bug.

Repository-specific interpretation: `servicing.py` persists and replays decisions by calling the
existing pure `domain.evaluate_servicing` engine. New claim-agent code must enter through the
existing servicing path; it may parse, validate, flag, route, or explain returned facts, but it may
not duplicate `domain.py` math, synthesize a financial result, accept a broker-typed payable amount,
or treat an LLM response as adjudication.

Baseline integrity at Phase 0:

- `backend/app/servicing.py` has no Phase 0 diff; stable Git blob ID
  `c77bb08ea2edcdda62a899ca183cb457bf32acf5`.
- `backend/app/domain.py` has no Phase 0 diff; stable Git blob ID
  `405fef374cd53b761085813a7f46639da942072a`.

## 7. Regulatory-source boundary

Phase 0 adds no medical or legal guidance to the product. The attached master plan's timer table is
design input, not a runtime source, and the exact PD-05-2025 document is not stored in this
repository. Before Phase 5 fixed emergency copy or Phase 7 SLA copy ships, those words and timers
must be checked against a current primary DHA/DHIC publication and retained as a source snapshot.
The [official DHA circular registry](https://services.dha.gov.ae/sheryan/wps/portal/home/circulars)
and an [official 2025 DHA standard](https://dha.gov.ae/uploads/012023/Standards%20for%20Telehealth%20Services2023158613.pdf)
located during this audit independently support electronic eClaimLink submission, but this code
audit does not claim that a secondary summary is a substitute for the underlying directive.

## 8. Verification

- `uv run pytest tests/test_servicing_domain.py tests/test_servicing_api.py -q` — **16 passed**.
- `uv run pytest -q` against the clean current remote baseline — **90 passed**.
- No frontend test/build was required because Phase 0 changes documentation only.

## Exit decision

Phase 0 is complete. Phase 1 may add only the three upstream staging tables. It must not alter
`servicing.py`, `domain.py` adjudication math, `servicing_events`, or the ledger projection contract.
Stop here; no Phase 1 code is included.
