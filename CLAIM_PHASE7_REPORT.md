# Claim Management Phase 7 Report

## Customer timeline

- `GET /api/policies/{policy_id}/claim-intakes` returns each member-owned intake with its current stage and the applicable regulatory target.
- The Claim Center renders intake, completeness/review, and decision stages.
- Emergency intakes show the no-prior-authorization/stabilization guidance and the seven-working-day post-approval target.
- Ordinary claims show the 45-calendar-day settlement target; reimbursement copy also identifies the 30-day resubmission target; pre-authorizations use the six-hour outpatient or 24-hour inpatient target.

## Straight-through performance

- `GET /api/broker/claims/analytics` derives the metric from existing `claim_intakes`, `claim_flags`, and servicing-event references.
- A straight-through intake is counted only when it has a decisive servicing event and has never had a claim flag.
- No tracking or analytics table was added.

## Explainable anomaly checks

- A repeated provider/benefit/amount submission within seven days creates an `anomaly` flag with that exact explanation.
- With at least three comparable prior submissions, an amount over three times the benefit-class median creates an `anomaly` flag naming both amounts.
- Either flag routes the intake to human review; there is no opaque risk score.

## Deterministic explanation

- The Claim Center states that the Claim Agent routes and explains but never sets approvals or payment amounts.
- Completed decisions expose the existing append-only calculation trace through the shared `CalculationStepper`.

## Verification

- `python -m pytest backend/tests -q`: **107 passed**
- `python -m ruff check backend/app backend/tests`: **passed**
- `npm run check`: **passed**
- `npm run build`: **passed** (existing Vite large-chunk warning only)
- `npx playwright test --workers=1`: **5 passed**

