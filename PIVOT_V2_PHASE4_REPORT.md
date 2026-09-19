# Marketplace Pivot v2 — Phase 4 report

Phase 4 adds catalogue-stage matching only. It stops before the Provider Workspace and real
quotation flow in Phase 5 and Phase 6.

## Matching design

`backend/app/agents.py::rank_catalogue_plans` is pure deterministic Python. It scores at most 100
points: price fit 35, coverage fit 40, and network fit 25. Price is weighted rather than used as a
cutoff, so a plan slightly above budget remains eligible. Ties resolve by premium, provider ID, and
plan ID.

Coverage checks call `backend/app/domain.py::evaluate_servicing` with the applicant's usable policy
month. This keeps covered, excluded, waiting-period, and `insufficient_data` decisions in the
existing servicing rules. A plan that produces `insufficient_data`, or lacks a term needed for the
applicant's situation, is excluded before the top five is selected.

`explain_catalogue_ranking` receives the fixed structured top five and makes one Groq call for all
five. The model returns explanation text keyed to those plan IDs; it cannot replace the score,
premium, factors, or ordering returned to the member.

## Worked synthetic example

Profile: AED 16,000 annual budget; UAE cover; wide network requested; maternity needed within 12
months with an 8-month maximum wait; declared chronic condition needing immediate cover.

| Rank | Fictional plan | Premium | Score | Structured fit factors |
| ---: | --- | ---: | ---: | --- |
| 1 | Helm Direct — Comprehensive | AED 16,500 | 98.91 | Price 33.91/35; maternity covered by month 8; chronic covered at month 0; wide network 25/25 |
| 2 | Al Noor Takaful — Standard 2 | AED 9,105 | 87.50 | Price 35/35; both declared benefits usable on time; standard network 12.5/25 |
| 3 | Gulf Shield Insurance — Wide 5 | AED 16,702 | 78.46 | Price 33.46/35; maternity usable; chronic wait not elapsed at month 0; wide network 25/25 |
| 4 | Pearl Health Partners — Standard 5 | AED 9,414 | 67.50 | Price 35/35; maternity usable; chronic wait not elapsed at month 0; standard network 12.5/25 |
| 5 | Union Assurance UAE — Standard 6 | AED 9,879 | 67.50 | Price 35/35; maternity usable; chronic wait not elapsed at month 0; standard network 12.5/25 |

The results are returned with raw component scores and benefit decision codes, followed by the
exact consent prompt: **“Would you like me to send your details to these providers for a real
quote?”** Fetching recommendations creates no applications.

## Consent boundary

The consent endpoint accepts only literal `yes` or `no`. `no` creates nothing. On `yes`, provider
IDs are deduplicated in top-five order, one `marketplace_applications` row is created per provider
at `broker_approved`, and the shared Phase 3 transaction guard immediately advances it to
`sent_to_providers`. Checkpoint 1 is checked before matching and again by that send guard. Emirates
ID and passport number are not copied into the provider consent snapshot.

## Verification

- Backend formatting/static checks: `uv run ruff check ...` — passed.
- Backend: `uv run pytest -q` — 83 passed.
- Frontend: `npm run build` — production build passed (existing bundle-size advisory only).
- Browser regression: `npx --prefix frontend playwright test --config playwright.config.ts
  --reporter=line` — 3 passed.
- Focused tests prove identical input produces identical top-five scores and order, a servicing
  `insufficient_data` decision is excluded, Groq is called once for the fixed five, `no` creates
  zero applications, and `yes` creates exactly one sent application per distinct provider.
