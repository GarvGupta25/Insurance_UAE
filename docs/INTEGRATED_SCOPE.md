# Integrated delivery scope

The application now follows the user's combined direction rather than treating either historic plan as exclusive.

The existing Phase 1 account, conversational profile, document extraction, quotation, Easy Fill, sandbox policy, payment, provider map and policy portfolio remain in scope. The integrated build now also includes Version 3's broker review, deterministic servicing, immutable history, appeal review and history-aware fit reassessment. Voice remains a shared input/output channel across both surfaces.

Where the plans conflict, these rules apply:

- A user still explicitly confirms an application and a test payment. A broker must approve or edit a recommendation before policy inception in the broker-enabled flow.
- The existing three supplied fictional plans remain the deterministic demo catalogue. Public-source research stays separately labelled until a reviewed plan source is available.
- Servicing decisions are calculation services. They never use the LLM to choose a rule or amount.
- A plan can be initially created through the sandbox flow, but its later servicing ledger is append-only and replayable.
- Real insurer issuance, carrier submission, payment capture and policy terms are never implied by the synthetic demo.
