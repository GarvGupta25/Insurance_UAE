# Synthetic demonstration script

Use only the three supplied fictional plans and fictional providers. Do not present a sandbox policy, simulated receipt, research link, or provider map entry as real insurance evidence.

1. Sign in with a synthetic account and show the empty dashboard.
2. Start a case. Use the conversation or structured editor to complete identity, health/cover, and payer/preference facts. Show that unknown remains unknown and that the profile persists.
3. Generate the indicative quotation. Compare the fictional plans, visible waits, network tradeoffs, and the PDF download.
4. Select a supported plan with Easy Fill. Show the saved-data application mapping and the broker review checkpoint.
5. In Broker workspace, approve the selected fictional plan. Return to the member application, acknowledge the exact snapshot, and create the sandbox policy.
6. Open Payments and simulate a successful receipt. State that no money moved and no policy was issued.
7. Open Servicing, submit a synthetic claim, and show the deterministic reason, calculation, and ledger. Submit an appeal and show the append-only broker result.
8. Run a fit reassessment, have the broker retain or recommend one of the supplied plans for a future review, and show that the active policy remains unchanged.

Verification before a demonstration: run backend tests and Ruff, then the frontend type check and production build. With local Supabase, API, worker and frontend running, also run `uv run python scripts/live_smoke.py` from `backend/`.
