# Helm AI project handover and requirements assessment

**Repository:** `GarvGupta25/Insurance_UAE`  
**Reviewed branch:** `main`, most recent committed revision `f4b1839`  
**Assessment basis:** source code, migrations, tests, scripts, existing documentation, the supplied fictional data, `revisedPLAN.md`, and the user's pasted Key Requirements.  
**Product boundary:** Helm AI is a local, synthetic UAE individual-health-insurance demonstration. It must never be presented as an insurer, policy issuer, real network directory, real underwriting system, or real payment processor.

## 1. What this project is trying to prove

Helm AI is a working prototype of a health-insurance brokerage journey. A person gives reusable insurance information by typing, using an editable profile, or optionally speaking. The system compares the three fictional plans supplied with the challenge, records an indicative recommendation, prepares a sandbox application, creates a fictional policy after confirmation, and supports later policy servicing.

The intended connected journey in the supplied requirements is:

```text
Intake → classification and flags → three-plan quote → reviewed recommendation
      → demo policy → pre-authorisation / claim / reimbursement / appeal
      → ledger history → policy-fit reassessment
```

The application deliberately divides responsibility:

| Responsibility | Current implementation |
| --- | --- |
| Interpret a natural-language message | Groq model through a bounded LangGraph worker; it can only propose a typed fact patch and short explanation. |
| Keep user facts | Versioned PostgreSQL profile records with source/provenance. |
| Decide eligibility, premiums, recommendations, benefit amounts, waits, deductible and co-pay | Deterministic Python code, never the model. |
| Approve/edit a recommendation or appeal | Assigned broker through explicit API actions. |
| Persist and rebuild benefit balances | Append-only servicing events and a replayed ledger projection. |
| Authenticate | Local Supabase Auth; the API verifies every bearer token with Supabase. |

This is the correct general architecture for an insurance prototype: the model helps with language and explanation, while prices, policy terms, authority and money calculations remain controlled by deterministic code.

## 2. Current repository architecture

```text
Browser (React/Vite, port 5174)
    │ Supabase session token + same-origin /api calls
    ▼
FastAPI (port 8000)
    ├─ verifies user with Supabase Auth
    ├─ uses SQLAlchemy/PostgreSQL for business records
    ├─ calculates quotes, applications, payments and servicing rules
    └─ queues conversational runs
             │
             ▼
LangGraph worker (separate Python process)
    ├─ reads queued message + scoped context
    ├─ calls Groq for JSON-only intake/policy assistance
    └─ saves an assistant message and proposed fact patch

Local Supabase / Docker
    ├─ Auth (email/password)
    ├─ PostgreSQL
    ├─ migrations and RLS
    └─ local Studio and API services
```

### 2.1 Technology inventory

| Area | Technology | Why it is present |
| --- | --- | --- |
| Frontend | React 19, TypeScript, Vite, React Router | Single-page public, member and broker experience. |
| Browser state | TanStack Query | Fetches/caches API records and invalidates them after mutations. |
| Icons and mapping | Lucide React, Leaflet | UI icons and optional fictional-provider map. |
| Backend | FastAPI, Pydantic, Uvicorn | Typed HTTP API and validation. |
| Data access | SQLAlchemy plus Psycopg | PostgreSQL sessions, transactions and database-backed LangGraph checkpoints. |
| Authentication/database | Local Supabase | Auth, PostgreSQL, migrations and row-level read controls. |
| Language and speech | Groq SDK | Structured assistant responses and optional speech-to-text. |
| Agent orchestration | LangGraph with PostgreSQL checkpointer | Durable queued assistant jobs, with a bounded single-node graph today. |
| Documents | ReportLab, PyMuPDF, Pillow, Tesseract | Indicative quote PDFs and optional identity-document extraction. |
| Payments | Local simulator; optional Razorpay test adapter | Demonstrates receipt flow without real payment. |
| Tests | Pytest, Ruff, Playwright | Domain/API/unit tests, linting and landing-page browser checks. |

### 2.2 Important directories and files

| Location | Contents |
| --- | --- |
| `frontend/src/main.tsx` | Routes, landing page, sign-in/up/recovery page, sidebar shell and role-gated Broker workspace link. |
| `frontend/src/Shopping.tsx` | Dashboard, case intake screen, quote comparison, Easy Fill/application confirmation and policy dashboard/servicing UI. |
| `frontend/src/ProfileEditor.tsx` | Three-stage editable profile form, conditional fields and identity-upload review controls. |
| `frontend/src/Conversation.tsx`, `Voice.tsx` | Chat composer, editable model-proposed patches, microphone recording/transcript review and browser read-aloud. |
| `frontend/src/Broker.tsx` | Broker recommendation, appeal and reassessment review screens. |
| `backend/app/main.py` | API endpoints and orchestration of business services. |
| `backend/app/contracts.py` | Pydantic schemas, question/readiness rules and request validation. |
| `backend/app/domain.py` | Catalogue adapter, cohorts, comparison, application mapping, schedules and deterministic servicing evaluator. |
| `backend/app/servicing.py` | Append-only event persistence and replayable ledger projection. |
| `backend/app/agents.py`, `worker.py` | Groq JSON interpreter and durable queue worker. |
| `backend/app/models.py` | SQLAlchemy model definitions. |
| `supabase/migrations/` | Database schema, RLS and broker/servicing extensions. |
| `backend/data/hackathon_data.json` | Unchanged fictional plan, applicant and servicing-event source data. |
| `backend/scripts/live_smoke.py` | Local end-to-end synthetic account, broker review, policy, claim and payment smoke test. |
| `backend/app/fixture_tour.py` | Deterministic all-five-applicant/all-thirteen-event fixture walkthrough. |
| `scripts/start-prototype.ps1` | Local prototype launcher and local demo-account bootstrap. |

## 3. Roles, visibility and demo accounts

The code implements two authorization roles and three practical demo personas.

| Persona | Login | Role resolved by API | Broker assignment | Intended use |
| --- | --- | --- | --- | --- |
| Member with broker | `member@example` / `password` | `member` | Assigned to `broker@example` | Demonstrate the broker-review route. |
| Assigned broker | `broker@example` / `password` | `broker` | Can see only assigned cases | Review requested plan recommendations, appeals and reassessments. |
| Regular member | `regular@example` / `password` | `member` | No broker assignment | Demonstrate member-only direct application route. |

`backend/scripts/bootstrap_demo_accounts.py` creates or repairs these local-only accounts. It assigns the broker role through `auth.users.raw_app_meta_data` and writes the member-to-broker mapping in `public.broker_assignments`. It does not store those credentials in the frontend or Git configuration.

### 3.1 Access enforcement

1. The browser sends a Supabase access token as `Authorization: Bearer …`.
2. `backend/app/auth.py` calls Supabase Auth’s `/auth/v1/user` endpoint instead of trusting browser-supplied IDs or locally decoded claims.
3. The backend takes the user ID and email from that verified response.
4. All ordinary records use `owner_id`; helper `own()` applies ownership to every lookup.
5. Broker access requires both `helm_role = broker` and a matching `broker_assignments` row. A broker role by itself gives access to no member case.
6. Browser roles cannot create or update assignments. The assignment table is revoked from `anon` and `authenticated` database roles.

### 3.2 Information the member can see

Members can see their profile, quotes, selected plan, visible reasons/tradeoffs, application state, demo policy, instalments/receipts, provider list, servicing result, appeal history and fit result. Their visible profile masks saved sensitive identity fields.

### 3.3 Information the broker can see

The broker API returns assigned pending recommendations, pending appeals and pending reassessments. Recommendation summaries contain a decision brief, certainty and plan reasons. This is useful operational data, but it is **not yet the complete broker record required by the pasted requirements**: the broker UI does not currently show a full applicant profile, all three quotes, all internal flags/firing reasons and complete utilization history in one case-detail screen.

## 4. Member workflow in detail

### 4.1 Sign-in and dashboard

1. The user opens `/login`, enters email/password and Supabase creates a persisted browser session.
2. Successful login routes to `/app`.
3. The Dashboard calls `/api/me/profile`, `/api/cases`, `/api/policies` and `/api/me/access`.
4. A new user sees a call to start a case. A returning user sees saved cases and demo policies.
5. Sign-out clears the Supabase session and query cache. A recent local improvement also attempts a local-only sign-out after an Auth-network failure so an old session does not trap the browser.

### 4.2 Intake: reusable profile and case

The member starts a `shopping_case`, then sees two linked intake tools on the Intake screen:

* **Conversation:** a text message is saved immediately, then a queued agent run processes it. The assistant responds with a short reply and may propose structured facts. The user must click **Save these details** before a proposed patch changes the profile.
* **Editable profile:** a three-tab form captures reusable facts directly. Existing facts remain visible, and saving one tab increments profile version and retains prior data.
* **Voice:** the member may tap Speak, record a short clip, review/edit the transcription and send it as a normal message. The raw audio is not persisted.

The short challenge profile currently uses these stages:

| Stage | Intended required data | Current implementation |
| --- | --- | --- |
| About you | Age, marital status, smoking declaration | Implemented. An optional display name is also present. |
| Health and upcoming care | Diagnosed-condition answer, named conditions when “yes”, near-term needs | UI field is implemented. The current working checkout is being updated so an explicit near-term need or “none” is required before quotation. |
| Budget and priorities | Budget category and priorities | Implemented. Optional monthly/annual preference is available. |

Facts have Pydantic validation. For example, an age must be 0–120; condition lists are bounded; `diagnosed_conditions = no` cannot be saved alongside named conditions; and unknown/declined are separate from no. Profile updates have optimistic version checks: a stale browser receives a 409 rather than overwriting another saved correction.

The editor also contains an optional extended application-oriented profile: legal name, date of birth, nationality, residency, emirate, payer, start date, maternity preferences, geography, network preference, funding fields and optional identity-document OCR. This extended path belongs to the earlier broader Phase 1 scope. It is not needed to price the three supplied flat-price challenge plans.

### 4.3 Conversational assistant lifecycle

1. `POST /api/cases/{case_id}/messages` stores the member text and a scoped context snapshot.
2. It creates an `agent_runs` row in `queued` state and returns a run ID.
3. `backend/app/worker.py` claims the row with a lease, loads the profile and up to eight prior case messages, then invokes the LangGraph graph.
4. `agents.interpret()` sends a constrained system prompt, accepted facts, the next missing question and record context to Groq.
5. Groq must return JSON with `reply`, `patch` and `sources`. Unsupported keys, invalid schema, sensitive ID fields and invalid/missing replies are rejected.
6. The worker records either a complete assistant message or an error-safe fallback message. It never logs the health prompt, Groq response or secret.
7. The frontend polls the case; if the assistant supplied a patch, the user explicitly accepts or discards it.

**Important runtime dependency:** API configuration may say AI is available whenever `GROQ_API_KEY` is non-empty, but the actual assistant also needs the separate `python -m app.worker` process. A Groq structured-response smoke call succeeded with the configured local model `openai/gpt-oss-20b`; the assistant outage found during this review was caused by the worker not running, not by an invalid Groq key. The local launcher has an uncommitted update to start the worker automatically. Until that is committed or started manually, chat messages can remain queued.

### 4.4 Classification, quote and recommendation

When the profile is ready, the member clicks **Get quotation**.

1. `POST /api/cases/{case_id}/quotes` uses `domain.compare()` against all three source-plan snapshots.
2. `domain.classify()` generates an internal cohort and age-band/need flags from typed facts. Examples include `general_needs`, `near_term_maternity`, `ongoing_chronic_care` and `complex_ongoing_care`.
3. The quote snapshot contains the three plans, their flat annual premiums, supported/unsupported status, reasons, gaps, waiting periods and tradeoffs.
4. The frontend shows a recommended plan and the alternative reasons. It can download a ReportLab PDF at `/api/quotes/{quote_id}/download`.
5. Quote data is a snapshot tied to `profile_version`; later material profile edits make old quote/application state stale rather than silently rewriting it.

This part aligns well with the Key Requirements: all three supplied plans are evaluated, and recommendation reasoning is deterministic and applicant-specific. The model does not pick prices or calculate tradeoffs.

### 4.5 Easy Fill, review and policy creation

1. The member selects a supported plan in the quote screen.
2. `POST /api/applications/prepare` runs deterministic `map_application()`, stores a payload hash and creates a `recommendations` record for a reviewable case.
3. The member sees the mapped fields and must explicitly confirm declarations using the current payload hash.
4. `POST /api/applications/{id}/submit` rejects stale snapshots and creates a `demo_active` policy only after its required state is met.
5. Policy creation freezes the selected plan snapshot and generates 12 monthly instalments or an annual schedule depending on the selected payment frequency.

**Current mismatch with the pasted Key Requirements:** current committed product behavior permits a regular member to prepare an ordinary supported application with `request_broker_review = false`, then confirm it directly. An assigned member can separately choose **Ask my assigned broker to review**, which blocks confirmation until a broker approves or edits. The pasted requirements say the reviewer **must** approve/edit every final recommendation. Therefore the direct route must be removed or changed to mandatory review before the project can be called compliant.

### 4.6 Policy, payments and provider lookup

The policy screen contains tabs for cover details, payments, servicing, history, fit and provider lookup.

* **Policy snapshot:** shows fictional plan terms and status `demo_active`.
* **Payments:** creates an idempotent payment order per saved instalment. The default simulator marks a synthetic receipt as captured; no funds move. The optional Razorpay adapter accepts only `rzp_test_` credentials, verifies provider payment amount/currency/order/signature server-side, then creates a receipt.
* **Providers:** filters fictional facilities by plan and emirate. Location is browser-only until the user requests it; the map loads OpenStreetMap only on demand. A nearby listing is explicitly not a real coverage/availability guarantee.

These payment/map/OCR features are above the core challenge scope. They are labelled synthetic/test-oriented in the UI and code, but they should not distract from the reviewer and servicing requirements.

### 4.7 Servicing workflow

The member can create a pre-authorisation forecast, claim or reimbursement request from the policy screen.

1. The member enters event reference, month, benefit class, provider tier, amount and description.
2. The browser calls `/api/policies/{id}/servicing/preview` for a non-mutating result.
3. An explicit submit calls `/api/policies/{id}/servicing` with expected policy version.
4. `evaluate_servicing()` applies the plan rules deterministically in integer fils and returns AED-ready fields.
5. `record_financial_event()` appends a decision row and calls `rebuild_projection()` to derive current balances from effective history.
6. The policy history and ledger cards refresh for the member.

The implemented evaluator follows the supplied contract:

| Rule | Current behavior |
| --- | --- |
| Gate order | Policy active → covered benefit → waiting period → network tier → sublimit → annual limit → calculation. |
| Network | A gate, never an out-of-network discount. |
| Deductible/co-pay | Deductible is applied first; co-pay then applies to remaining eligible amount. |
| Sublimit | Caps the insurer/plan payment after co-pay, not the billed amount. |
| Claim consumption | Only a covered financial claim/reimbursement affects ledger balances. Denials and pre-auth forecasts do not debit it. |
| Inpatient/outpatient | Same supplied copay percentage is used. |
| Abroad treatment | Returns `insufficient_data`; it does not invent geographic policy terms. |
| Reason codes | Returns the specified codes: `covered`, `policy_not_active`, `benefit_excluded`, `waiting_period_not_elapsed`, `provider_out_of_network`, `sublimit_exhausted`, `annual_limit_reached`, and `insufficient_data`. |

### 4.8 Appeals and fit reassessment

* **Appeal:** a member can appeal a denied claim/reimbursement with a statement and evidence references. The original decision remains immutable. The broker can uphold or overturn only with an accepted correction: a corrected policy month or verified network membership. Overturning appends review/revision records and replays later effective events.
* **Fit reassessment:** a member requests a report comparing current profile facts and effective servicing history to the frozen plan and alternatives. It records an informational result; it does not change coverage. A broker can record retain or recommend a future alternative.

The current implementation chooses broker review for appeals and reassessments. Routine determinate claims are system-decided, which is a defensible checkpoint choice. The future requirement is to document that choice clearly in the broker worklist and written deliverable.

## 5. Assigned broker workflow in detail

### 5.1 Broker workspace entry

The `/app/broker` route is shown only when `/api/me/access` returns `role: broker`. The broker session uses its own Supabase account. The backend rejects member access with 403 and rejects a broker who is not assigned to the member’s record with 404.

### 5.2 Recommendation review

1. The broker calls `GET /api/broker/recommendations`.
2. The route joins recommendations to `broker_assignments` and returns only assigned cases.
3. Each card shows the selected plan, certainty label, decision brief, reasons/tradeoffs and supported alternatives.
4. The broker chooses **Approve recommendation** or selects a different supported plan and records a note.
5. `POST /api/broker/recommendations/{id}/review` appends a `ReviewDecision`, updates the recommendation/application state and records audit information.
6. The member refreshes the application and can then complete explicit confirmation when the application requires broker review.

### 5.3 Appeal review

1. The broker reads `GET /api/broker/appeals`.
2. The view shows member statement, evidence references and original decision.
3. The broker either upholds the decision or supplies the specific correction required to overturn it.
4. The review route appends servicing records rather than editing prior decision data, then triggers ledger replay.

### 5.4 Fit-review work

The broker reads `GET /api/broker/reassessments`, reviews findings and alternatives, then records **retain** or **recommend change**. This records a future recommendation only; active policy terms never change automatically.

### 5.5 Broker gaps versus the Key Requirements

The broker workspace exists and has functional review controls, but it is not yet the substantial, prioritized case-management surface requested. Missing or incomplete pieces are:

* No unified worklist that combines pending recommendations, flagged applicants, appeals and `insufficient_data` servicing outcomes.
* No documented sorting rule using actual urgency, missing data and age of unresolved work.
* No complete case-detail view with profile, all three quote alternatives, cohort, flags/firing reasons, full policy/event history and utilization together.
* Internal cohort/flag details are computed in quote data, but are not presented as a distinct broker-only operational explanation.
* Recommendation status is optional for regular member Easy Fill, contrary to mandatory reviewer approval.

## 6. Data model and persistence

### 6.1 Core ownership/version records

| Table/model | Purpose | Key fields and rules |
| --- | --- | --- |
| `profiles` | Current reusable member facts | One per owner, JSON facts/provenance, integer version. |
| `profile_versions` | Historical profile snapshots | One append-only row per accepted version. |
| `shopping_cases` | A member’s intake/quote journey | Owner, state/status and creation timestamp. |
| `messages` | Typed/voice conversation messages | Role, modality, text and scoped context. Raw audio is absent. |
| `agent_runs` | Durable assistant jobs | Queue/running/complete/failed status, attempts, lease and result. |
| `quotes` | Immutable three-plan indicative quote | Case, profile version and full snapshot. |
| `applications` | Prepared application mapping | Quote, optional recommendation, state, snapshot and confirmation hash. |
| `recommendations` | Reviewable selection | Proposed plan, certainty, decision brief and review status. |
| `review_decisions` | Broker action record | Before/after snapshots, note, recommendation/appeal/reassessment relation. |

### 6.2 Policy, payment and servicing records

| Table/model | Purpose | Key fields and rules |
| --- | --- | --- |
| `policies` | Frozen fictional policy snapshot | `demo_active`, application relationship and policy version. |
| `instalments` | Scheduled synthetic payments | Position, due date, amount in fils, unique per policy position. |
| `payment_orders` / `receipts` | Payment intent and settled receipt | One receipt/order and one receipt/instalment; server-calculated amount. |
| `servicing_events` | Append-only source, decision, appeal, review and revision log | Root event ID, sequence, payload, outcome, reason, calculations, ledger before/after and `supersedes_id`. |
| `benefit_ledger_projections` | Derived current balance | Disposable/rebuildable projection; not source of truth. |
| `policy_reassessments` | Saved fit reports | Profile version, report, reviewed/future recommendation state. |
| `audit_events` | Trace of backend mutations | Action, subject and safe details. |
| `command_receipts` | Idempotency | Same owner/key/payload replays safely; changed payload returns 409. |

### 6.3 Database protections

Migrations enable RLS across browser-exposed tables. `anon` and `authenticated` roles lose direct write access. Select policies are restricted by `owner_id = auth.uid()` where member reads are supported. The FastAPI server owns mutations. LangGraph checkpoint tables also have RLS enabled/revoked at worker startup because checkpoints may contain sensitive context.

Sensitive identity values are encrypted only when the configured document-encryption key exists, then masked when returned to the member. The project does not put Groq keys, Supabase service keys or raw profile details in source control.

## 7. API inventory

### 7.1 Public/runtime endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health`, `GET /ready` | Liveness and database readiness. |
| `GET /api/config` | Frontend capabilities: Auth, AI, voice and payment mode. |
| `GET /api/catalogue` | Three fictional plan source objects. |
| `GET /api/sources` | Separately labelled public research registry; never used as live quote terms. |

### 7.2 Profile, case, assistant and quote endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET/PATCH /api/me/profile` | Read/update reusable profile with expected version. |
| `GET/POST /api/cases`, `GET /api/cases/{id}` | Create/list/read member case and messages. |
| `POST /api/cases/{id}/messages`, `GET /api/runs/{id}` | Queue assistant job and obtain result/status. |
| `POST /api/voice/transcriptions` | Bounded audio validation, Groq transcription and editable transcript. |
| `POST /api/documents`, `POST /api/extractions/{id}/accept` | Optional identity extraction and explicit acceptance. |
| `POST /api/cases/{id}/quotes`, `GET /api/quotes/{id}`, `GET /api/quotes/{id}/download` | Create/read/download immutable indicative quote. |

### 7.3 Application, broker and policy endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/applications/prepare`, `GET /api/applications/{id}`, `POST /api/applications/{id}/submit` | Prepare mapped application, view current snapshot, member-confirm and create demo policy. |
| `GET/POST /api/broker/recommendations…/review` | Assigned broker queue and approval/edit action. |
| `GET /api/policies`, `GET /api/policies/{id}` | Member policy portfolio and full policy state. |
| `POST /api/policies/{id}/reassess` | Generate persisted policy-fit report. |
| `GET/POST /api/broker/reassessments…/review` | Broker fit review. |

### 7.4 Servicing and payment endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /api/policies/{id}/servicing/preview` | Non-mutating pre-check of a service request. |
| `POST /api/policies/{id}/servicing` | Append a claim, pre-auth or reimbursement decision and rebuild ledger. |
| `POST /api/policies/{id}/appeals` | Member appeal against a denied decision. |
| `GET/POST /api/broker/appeals…/review` | Broker uphold/overturn action. |
| `POST /api/instalments/{id}/payment-order` | Create local/Razorpay test order. |
| `POST /api/payment-orders/{id}/simulate` | Explicit local simulator capture/failure/cancellation. |
| `POST /api/payments/verify`, `POST /api/webhooks/razorpay` | Verify optional Razorpay test provider result. |
| `GET /api/policies/{id}/updates`, `GET /api/providers` | Fictional policy updates and provider directory. |

## 8. Test evidence and fixture coverage

The repository contains backend tests for contracts, source fixtures, deterministic servicing, broker authorization/assignment, API ownership, appeals/replay, worker behavior, sources and voice. The fixture tour confirms:

* all five supplied applicants are parsed from the unchanged source fixture;
* every applicant receives all three plan comparisons;
* recommendations are generated from intake facts rather than future servicing outcomes;
* all thirteen supplied events run in the specified order;
* outcomes, plan/member payments, reason codes and final ledgers match the fixture expectation;
* the intentionally unknown overseas reimbursement ends as `insufficient_data`;
* APP-1 is upheld and APP-2 is overturned only with separate broker-accepted network evidence.

At the earlier committed verified state, the repository recorded 56 backend tests, Ruff, TypeScript check and production build passing. The current working directory has uncommitted feature work, including the near-term-needs intake fix and launcher worker start. During this review the partial change caused two fixture-profile test failures until the fixture expectations/data adapter are reconciled. Therefore the old “56 tests passed” statement is historic evidence, **not** proof that the exact current checkout is green. The next implementation task must finish those edits and rerun the full suite before claiming a clean build.

## 9. Requirement-by-requirement assessment

| Pasted Key Requirement | Current status | Evidence / reason |
| --- | --- | --- |
| Intake captured once and reusable | **Mostly done** | Versioned profile, case messages and manual/voice paths exist. Near-term needs has only just been made required in the uncommitted checkout. |
| Eligibility classification and flags | **Partly done** | Deterministic cohorts and quote certainty exist; full broker-visible flags/firing explanations do not. |
| All three supplied plan quotes | **Done** | `compare()` evaluates all source plans and quote snapshots preserve reasons/tradeoffs. |
| Specific recommendation and losing-plan reasons | **Done** | Quote/recommendation snapshots include selected reasons and alternatives. |
| Mandatory reviewer approval before final recommendation | **Not done** | Direct Easy Fill remains possible for regular members. Broker review is opt-in/assignment-dependent. |
| Policy and shared ledger after approval | **Mostly done** | Demo policy and replayed ledger exist; direct application path needs mandatory-review correction. |
| Pre-auth / claim / reimbursement | **Done in deterministic engine** | One evaluator and explicit preview/submission routes. |
| Appeal upheld/overturned with replay | **Done** | Append-only review/revision and replay implementation plus tests/fixture tour. |
| History-based plan-fit assessment | **Mostly done** | Reassessment reads effective history and current facts; depth/presentation is limited. |
| Exact evaluator arithmetic and reason codes | **Done in code/tests** | Deterministic servicing tests/fixture tour cover gates, waits, network, deductible/co-pay, sublimit and abroad. |
| Append-only source event log / rebuildable ledger | **Done** | `servicing_events` and `rebuild_projection()`. |
| Persist across browser restart | **Done locally** | Supabase/PostgreSQL ownership records and browser session. |
| Thin customer view | **Mostly done** | Member screens expose policy, payment, servicing and history, though pending-item polish remains. |
| Substantial prioritized broker worklist/full record | **Not done** | Separate lists exist but no unified priority ordering or comprehensive case detail. |
| Customer/broker explanations written separately | **Partly done** | Broker summaries and member policy content differ, but no formal two-audience explanation model/acceptance test. |
| All five applicants and 13 events captured in working demo | **Partly done** | Deterministic fixture tour runs all data, but results are not yet exposed as a complete captured website/report deliverable. |
| Three-minute demo/video and written judging answers | **Not done** | A walkthrough script exists; no final video or all requested written answers bundle. |
| Voice as bonus | **Implemented but operationally fragile** | Shared recording/transcript/read-aloud code exists; live assistant depended on missing worker startup. |

## 10. Work remaining, why it matters, and recommended order

### Priority 1 — restore dependable prototype operation

1. **Finish and commit the worker-start launcher change.** The API alone cannot process assistant messages. The launcher must reliably start Supabase, FastAPI, the LangGraph worker and Vite; it should wait for health/readiness before showing the URL.
2. **Complete the near-term-needs readiness change and update fixture adapter/tests.** The source applicants contain near-term needs. A quote should not be marked ready until a member supplies a need or explicit “none.” This preserves the “capture once” requirement without re-asking later.
3. **Run the full tests, Ruff, frontend type check/build and a live Groq smoke test.** The current source has interrupted uncommitted work, so test results must be refreshed before further feature claims.

### Priority 2 — make the connected core compliant

4. **Make broker recommendation review mandatory.** Every recommendation must create/retain a pending review record; no member route may create a policy while pending. If a demo needs a member without a human broker, seed a designated review account or show an explicit pending state—do not bypass the checkpoint.
5. **Ensure flagged/intentionally unknown work reaches the broker.** `insufficient_data`, flagged cohorts, recommendation uncertainty and appeals should all create or surface an assigned review task.
6. **Add a unified broker worklist with a documented priority score.** Suggested deterministic ordering: overdue/aged unresolved work first; then coverage-blocking `insufficient_data` and appeals; then pending recommendation uncertainty/flags; then routine clear recommendations. Store/display the reasons for priority.
7. **Build a broker case-detail view.** It must show profile, cohort/flags and why, three quote outcomes, recommended/losing-plan reasons, reviewer history, policy terms, all effective and superseded servicing records, ledger/utilization and pending next actions.

### Priority 3 — complete evidence and experience

8. **Implement separate member and broker explanation DTOs/templates.** Member text should describe coverage, outcome and next step plainly. Broker text should add routing/flags, uncertainty, evidence and review rationale. Do not merely hide paragraphs in a shared explanation.
9. **Expose the five-applicant/thirteen-event fixture tour as a report.** Persist/capture its outputs or generate a reproducible markdown/JSON/PDF artifact for judging, including each event’s outcome, plan payment, member payment, reason code and post-event ledger.
10. **Improve assistant failure visibility.** The UI should show “assistant worker unavailable/queued too long” with a retry control and preserve text. `/api/config` should distinguish “key configured” from “worker healthy/model reachable.”
11. **Broaden voice only after the text workflow is stable.** Intake voice works as transcript → member confirmation → normal message. Voice drafting for servicing, appeals and broker notes is still incomplete against the revised plan.
12. **Prepare final deliverables.** Create a concise demo script/video, written answers for all requested judging questions, and a final requirements traceability table.

### Lower-priority or deliberately out-of-scope items

Real insurance issuance, real carrier portals, real payment/billing, procedure coding, clinical necessity review, family/group policies, renewal, production hosting and regulatory approval should remain out of scope. OCR, provider maps, public-source research and Razorpay test support are useful demonstrations but are not substitutes for the mandatory reviewer/broker core.

## 11. How to run the local prototype

1. Start Docker Desktop and wait for **Engine running**.
2. In the repository root, run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\start-prototype.ps1
   ```

3. Open `http://127.0.0.1:5174/login`.
4. Use one of the local demo accounts from section 3.

Until the worker-launch edit is committed, start it manually after the API:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.worker
```

Useful validation commands:

```powershell
# Backend
cd backend
uv run ruff check app scripts tests
uv run pytest -q
uv run python -m scripts.fixture_tour
uv run python scripts.live_smoke.py

# Frontend, from repository root
npm run check
npm run build
npm run test:e2e
```

The live smoke script creates disposable synthetic accounts. It validates a member → assigned broker review → policy → claim → payment-receipt flow. It does not use a real carrier, issue a real policy or move money.

## 12. Current working-tree caution

The current checkout is not identical to GitHub `main`. It has uncommitted tracked changes in backend contracts/API/tests, profile/quote styling UI, and the prototype launcher, plus untracked presentation artifacts. Those edits include attempted fixes for assistant startup, intake readiness and previous usability work. They should be reviewed, completed and tested as one intentional change set; they must not be presented as already shipped until committed and pushed.

## 13. Final conclusion

Helm AI has a strong deterministic insurance-service core: source-plan comparison, exact servicing arithmetic, append-only/replayable event history, appeal revision and role-scoped backend access are materially implemented. It also has a polished local member flow and useful synthetic extensions such as voice transcription, PDFs and sandbox payments.

The project is not yet compliant with the pasted Key Requirements as an end-to-end brokered challenge delivery. The most important missing behavior is mandatory reviewer approval for every recommendation, followed by the required substantial prioritized broker worklist/full case record and a captured all-fixture deliverable. The current assistant issue is operational rather than a Groq-key failure: its worker process must be launched reliably. Fixing those items before adding more optional product features will produce the clearest, most defensible final prototype.
