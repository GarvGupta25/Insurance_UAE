# Marketplace Pivot v2 — Phase 7 Report

## Outcome

Phase 7 adds the marketplace transparency layer without introducing another tracking table or message transport. Member progress, provider performance, anomaly escalation, and workspace refresh all derive from the application, quotation, audit, and policy records already created by Phases 2–6.

## Member status timeline

The member marketplace page now renders six plain-language stages directly from `marketplace_applications.status`:

1. Sent to providers
2. Quotations ready
3. Quotation selected
4. Provider accepted
5. Final broker review
6. Policy started

Completed, current, and future steps have distinct accessible states. The status header and timeline refresh from the persisted API every five seconds until the case reaches a terminal state.

Evidence: `PIVOT_V2_PHASE7_MEMBER_TIMELINE.png`.

## Provider performance

`GET /api/broker/marketplace/provider-performance` computes two metrics without stored aggregates:

- Average response time: `provider_quotations.submitted_at - marketplace_applications.created_at`
- Win rate: quotations currently `selected` or `accepted` divided by all submitted quotation rows

The provider seed now creates one idempotent synthetic performance example per marketplace provider. Every example has the same sent time. Pearl Health Partners submits after 2 hours, ahead of Al Noor at 12 hours, Gulf Shield at 18 hours, and Union Assurance at 24 hours. Pearl is therefore visibly and mathematically fastest; the UI marks whichever provider is actually first in the computed result rather than hard-coding that conclusion.

Evidence: `PIVOT_V2_PHASE7_BROKER_PERFORMANCE_DESKTOP.png` and `PIVOT_V2_PHASE7_BROKER_PERFORMANCE_MOBILE.png`.

## Explainable anomaly detection

When consent creates a provider application, a deterministic rule checks for an earlier application with the same member, provider, and shared profile in the preceding ten minutes. A match writes a `marketplace_anomaly_flagged` event into the existing append-only `audit_events` table with the exact rule and reason.

The existing broker worklist reads unresolved anomaly audits and presents them as its existing high-priority `provider_flag` item type. There is no LLM judgment, duplicate inbox, or new anomaly table. Bound or declined applications naturally leave the active queue.

Automated evidence verifies two matching applications produce exactly one broker worklist flag for the second case.

## Cross-workspace refresh

The Phase 0 report described an in-process `events.py` bus, but no such file or bus exists in the current `main` history. Creating a replacement would still be unreliable across API workers and restarts. Phase 7 therefore uses the plan's documented fallback: short polling against persisted state.

- Member marketplace status: every 5 seconds
- Provider application, quotation, and policy views: every 5 seconds
- Broker worklist, application badges, case detail, and performance: every 5 seconds

The full lifecycle test proves one persisted transition is immediately readable by the other roles: member selection appears to the selected provider, provider acceptance appears in the broker worklist and member status, broker approval appears in member status, and provider binding appears as the member's final `bound` state. Polling only controls when the UI fetches that authoritative state; it does not maintain a second copy.

## Verification

- Backend: `89 passed`
- Ruff: passed
- Frontend production build and type-check: passed
- Playwright: all `5` browser journeys passed in serial verification
- Seed verification proves Pearl Health Partners is first at 2 hours and rerunning the seed creates no duplicates
- Existing non-blocking warnings remain: Starlette's upstream AnyIO deprecation warning and Vite's optional bundle-size advisory
