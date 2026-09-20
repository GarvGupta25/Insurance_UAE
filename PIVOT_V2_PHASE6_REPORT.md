# Marketplace Pivot v2 — Phase 6 Report

## Outcome

Phase 6 completes the real provider-quotation path from collection through binding. The member's marketplace page now performs catalogue consent, waits for real provider responses, ranks at most three submitted quotations, records one selection, and shows the subsequent provider-acceptance and broker-review state. Bound marketplace policies appear in the correct member, provider, and broker views.

## Collection and ranking rules

- Collection is checked on demand whenever the member opens or polls marketplace status.
- Results open when every invited provider has submitted, or after 72 hours when at least one provider has responded.
- Before that condition, no partial ranking is shown.
- Ranking reuses the Phase 4 deterministic price (35), coverage (40), and network (25) calculation.
- The catalogue adapter is populated only from `provider_quotations.premium` and `provider_quotations.plan_terms`. Catalogue estimates are not read during real-quotation ranking.
- Provider quotation terms are now validated as complete structured terms at submission time.
- Groq, when configured, explains the fixed top three in one call; it cannot alter scores, premiums, terms, or ordering.

## Selection and binding

Selecting a quotation changes it to `selected`, changes every competing quotation for the same case to `declined`, changes the selected provider application to `customer_selected`, and declines the other provider applications. The provider workspace polls its persisted quotation list every five seconds, so the selected provider sees the acceptance action without relying on an ephemeral browser-only state.

The Phase 0 report referenced `events.py`, but that file and event bus are not present in the repository history currently on `main`. Phase 6 therefore uses persisted status plus bounded polling rather than inventing a new transport. This is restart-safe and does not falsely claim cross-process real-time delivery.

Provider acceptance advances only the selected application to `provider_accepted`, which immediately creates the existing Phase 3 Checkpoint 2 worklist condition. Policy start continues to fail until the assigned broker records Checkpoint 2. After approval, the provider can start exactly one policy and the application becomes `bound`.

## Fully traced test example

`backend/tests/test_marketplace_selection.py` runs this complete path:

1. One member case is sent to two isolated seeded providers.
2. Provider A submits complete terms at AED 8,000.
3. The member checks status; collection remains closed at one of two responses.
4. Provider B submits complete terms at AED 9,000.
5. Collection opens and real submitted figures rank AED 8,000 first and AED 9,000 second.
6. The member selects the first quotation; the second is automatically declined.
7. The selected provider accepts; policy start is rejected before Checkpoint 2.
8. The assigned broker sees the pending marketplace item and approves Checkpoint 2.
9. The selected provider starts the policy.
10. The policy is visible to the owning member, selected provider, and assigned broker.
11. It is absent for another member and the other seeded provider; the other provider also receives `404` when addressing its financial-account path directly.

## UI evidence

- Member comparison and recorded selection: `PIVOT_V2_PHASE6_MEMBER_SELECTION.png`
- Automated browser journey: `tests/e2e/marketplace-selection.spec.ts`

The dashboard links each case to its marketplace journey and lists bound marketplace policies separately from the original Helm Direct sandbox policies.

## Verification

- Backend: `86 passed`
- Ruff: passed
- Frontend type-check and production build: passed
- Playwright: `5 passed`
- Existing build advisory: the Vite bundle remains above its optional 500 kB warning threshold.
- Existing warning: Starlette's TestClient reports one upstream AnyIO deprecation warning.
