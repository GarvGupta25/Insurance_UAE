# Marketplace Pivot v2 — Phase 5 Report

## Outcome

Phase 5 adds the provider stakeholder surface at `/provider`. Provider identity is derived from the authenticated user's `provider_users` row; no provider endpoint accepts a provider ID from a request. The workspace covers received applications, consented profile review, quotation submission, selected-quotation acceptance, Checkpoint-2-gated policy start, policy discontinuation, simulated financial accounts, broker flags, and a narrowly scoped drafting aid.

## Backend and access boundary

- `require_provider` accepts only an administrator-controlled `helm_role=provider` claim and resolves the provider tenant from `provider_users`.
- Every record lookup includes the resolved `provider_id`; another provider's records return `404`, avoiding both access and existence disclosure.
- The application list exposes only `consent_snapshot`, status, ID and received time.
- A quotation can be submitted only for a `sent_to_providers` application and accepted only after customer selection.
- Policy start reuses the Phase 3 binding guard, requiring an accepted quotation and a distinct approved Checkpoint 2 decision.
- Discontinuation reasons are persisted; financial records and flags are policy- and provider-scoped.
- The provider drafting aid receives one already-scoped application and has no provider-selection input or cross-tenant query path.

## Cross-provider isolation evidence

`backend/tests/test_provider_console.py::test_every_provider_endpoint_is_tenant_scoped` signs in as Provider A and attempts every Phase 5 operation against Provider B. Each returns `404`:

| Endpoint | Provider A acting on Provider B | Result |
| --- | --- | --- |
| `GET /api/provider/applications` | list data | Only Provider A application returned |
| `POST /api/provider/applications/{id}/quote` | Provider B application | `404` |
| `GET /api/provider/quotations` | list data | No Provider B quotation returned |
| `POST /api/provider/quotations/{id}/accept` | Provider B quotation | `404` |
| `POST /api/provider/policies/{id}/start` | Provider B quotation | `404` |
| `GET /api/provider/policies` | list data | No Provider B policy returned |
| `POST /api/provider/policies/{id}/discontinue` | Provider B policy | `404` |
| `GET /api/provider/policies/{id}/payments` | Provider B policy | `404` |
| `POST /api/provider/policies/{id}/flags` | Provider B policy | `404` |
| `POST /api/provider/applications/{id}/assistant` | Provider B application | `404` |

The lifecycle test additionally proves that acceptance fails before customer selection, policy start fails before Checkpoint 2, and succeeds after the independent broker approval.

## UI evidence

- Desktop: `PIVOT_V2_PHASE5_PROVIDER_DESKTOP.png`
- Mobile: `PIVOT_V2_PHASE5_PROVIDER_MOBILE.png`
- Automated journey: `tests/e2e/provider-workspace.spec.ts`

The frontend checks `/api/me/access`, redirects provider accounts from `/app` to `/provider`, and still relies on backend enforcement for every data operation.

## Verification

- Backend: `85 passed` (`python -m pytest backend/tests -q`)
- Provider isolation/lifecycle: `3 passed`
- Frontend type-check: passed
- Frontend production build: passed
- Provider Playwright journey and responsive screenshots: `1 passed`

One existing Starlette deprecation warning remains. Vite reports its existing large-bundle advisory; neither is a test or build failure.
