# Claim Management Phase 3 Report

## Straight-through threshold

An intake is eligible for straight-through processing only when its claimed
amount is **strictly below 10% of the bound policy's annual limit**. The rule
is evaluated as `amount < annual_limit * 0.10`, in AED.

This uses a plan-relative threshold rather than one fixed AED amount: a claim
that materially affects a lower-limit plan receives the same review treatment
as a proportionally equivalent claim on a higher-limit plan. At or above the
threshold, Helm creates an open `high_value` flag and routes the intake to the
Phase 4 human-review queue.

## Boundary confirmation

`claim_agent.py` calls the unchanged `servicing.record_financial_event` only
after the document, flag, and threshold gates pass. It stores only that
append-only servicing event ID on the intake for traceability and reuses
`servicing_explanation` for member copy. It does not calculate an outcome,
reason code, plan payment, or member payment.

The existing `claim_flags` schema has no `insufficient_data` flag type. When
the deterministic engine returns that result, Phase 3 creates an open
`exclusion_risk` flag with an explicit `insufficient_data` reason so it is
visible to the Phase 4 reviewer queue.
