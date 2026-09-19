# Helm AI Marketplace Pivot v2 — Phase 1 Report

**Phase:** Intake Agent rebuild

**Date:** 19 September 2026

**Result:** Complete

## Outcome

The previous single-node, free-form intake interpreter has been replaced by an explicit LangGraph state machine in `backend/app/agents.py`. Python determines the active field, question order, applicability of conditional questions, validation, advancement, completion, and broker-review confirmation. Groq is limited to phrasing one predetermined question, extracting only the active field, and phrasing the final summary.

The existing policy Q&A behavior remains a separate `policy_assistant` node and is selected only when the server supplies policy context.

## Persisted state

The graph state now contains:

- `intake_fields`: every possible intake question with `value` and `answered`.
- `current_node`: the active question or `intake_complete`.
- `stage`: `collecting`, `complete_pending_confirmation`, `confirmed_for_review`, or `paused`.
- `awaiting_answer`: distinguishes a newly entered node from a reply to its question.
- `turn_patch`: carries one validated field to the existing member review UI while the graph transitions to the next node.

Production continues to use LangGraph's PostgreSQL checkpointer with thread ID `<owner_id>:<case_id>`. A resumed invocation merges accepted profile facts into the persisted state, skips answered fields without a Groq call, and continues at `current_node`. The worker recursion limit was raised from 8 to 64 so a profile completed through the structured editor can safely skip across all already-answered nodes.

## Node order

The required base nodes follow the existing `contracts.readiness()` order:

1. `legal_name`
2. `date_of_birth`
3. `nationality`
4. `residency`
5. `emirate`
6. `emirates_id_status`
7. `diagnosed_conditions`
8. `smoker`
9. `maternity`
10. `geography`
11. `start_date`
12. `near_term_needs`
13. `maximum_maternity_wait` — only when maternity is requested
14. `conditions` — only when diagnosed conditions are declared
15. `immediate_chronic_cover` — only when diagnosed conditions are declared
16. `payer`
17. `annual_budget`
18. `strict_budget`
19. `payment_frequency`
20. `company_name` — only for employer funding
21. `sponsor_name` — only for sponsor funding
22. `contribution_aed` — only for employer or sponsor funding
23. `intake_complete`

The graph also contains non-question routing nodes `bootstrap` and `policy_assistant`. Every possible question has its own graph node. Conditional nodes remain in the compiled graph but are never routed to when they do not apply.

## Control and model boundaries

- `bootstrap` deterministically finds the first applicable unanswered field.
- A field node with an accepted value skips immediately without calling Groq.
- An unanswered field makes one narrowly scoped phrasing call and ends the turn.
- Its reply makes one narrowly scoped extraction call. The returned value is validated through the existing `Facts` Pydantic model.
- `NEEDS_CLARIFICATION`, invalid JSON, a wrong shape, an empty required value, or failed Pydantic validation keeps the same node active and rephrases only that same question.
- Successful validation marks only that field answered and routes deterministically to the next applicable node.
- The completion node is reachable only when every applicable field is answered. It summarizes the collected facts, then asks exactly: “Would you like me to prepare this for broker review?”
- A strict affirmative sets `confirmed_for_review`; no or an unclear response sets `paused`. A paused completed intake can later be reopened and confirmed.

The existing `Facts` schema remains the single validation authority. A missing `near_term_needs` prompt was added to `contracts.PROMPTS`; explicit “none” is represented as `["none"]` so it is distinguishable from an unanswered empty list.

## Required tests

`backend/tests/test_intake_state_machine.py` adds the four specified tests:

| Test | Result | Evidence |
| --- | --- | --- |
| a. Full linear run | Pass | Every applicable field is phrased and extracted exactly once; no duplicate or skipped field; final yes reaches `confirmed_for_review`. |
| b. Interrupted and resumed | Pass | After three answers, a newly compiled graph using the same checkpointer resumes at the fourth field and never asks the first again. |
| c. Unusable answer | Pass | `NEEDS_CLARIFICATION` leaves the field unanswered, rephrases the same question, and does not advance. |
| d. Completion answered no | Pass | Stage becomes `paused`, `ready_for_broker_review` is false, and the database still contains zero recommendations. |

## Recommendation handoff constraint

The phase prompt asks completion to create/update a recommendation “exactly as the pre-rebuild code did.” The actual pre-rebuild code did not create a recommendation at intake completion. `Recommendation` requires both a valid `quote_id` foreign key and a `proposed_plan_id`; those do not exist until after deterministic quotation and plan selection.

Creating a row during intake would require fabricated identifiers and violate the current schema. This phase therefore emits the explicit, persisted `confirmed_for_review` stage and `ready_for_broker_review: true` handoff. Phase 3 must consume that handoff when it introduces Checkpoint 1 and its valid marketplace review record.

## Verification

Focused validation:

```text
ruff check app/agents.py app/contracts.py app/worker.py \
  tests/test_intake_state_machine.py tests/test_worker.py
All checks passed

pytest -q tests/test_intake_state_machine.py tests/test_worker.py \
  tests/test_fixture_profiles.py
13 passed
```

Full backend test suite:

```text
pytest -q
74 passed, 1 third-party deprecation warning
```

The full-repository Ruff command is not green because of pre-existing lint failures in the uncommitted public-assistant/staff-console work (`events.py`, `main.py`, `models.py`, `public_assistant.py`, `staff.py`, and their tests). The Phase 1 files themselves pass Ruff. Those unrelated working-tree files were preserved and were not reformatted or included in this phase.

## Regression boundary

- `backend/app/domain.py`: unchanged.
- `backend/app/servicing.py`: unchanged.
- Pricing, eligibility, comparison, application mapping, servicing evaluation, policy ledger, public assistant, and staff escalation behavior were not modified by Phase 1.
- All 74 backend tests pass.

## Files changed by Phase 1

- `backend/app/agents.py`
- `backend/app/contracts.py`
- `backend/app/worker.py`
- `backend/tests/test_intake_state_machine.py`
- `PIVOT_V2_PHASE1_REPORT.md`
