# Claims Phase 0–1 setup

Phase 0 is the existing claim workflow. Phase 1 adds findings, immutable claim audit records, the member advocate, and broker paging.

Apply `supabase/migrations/202609230001_agentic_claims_phase_one.sql` before starting the updated API. The local Supabase database must be running.

Set these variables in `backend/.env`:

```text
ONCALL_WEBHOOK_URL=https://your-private-paging-endpoint.example/claims
ONCALL_WEBHOOK_TOKEN=your_paging_token
ONCALL_RESPONSE_TARGET_MINUTES=15
CLAIM_CONFIDENCE_THRESHOLD=0.6
CLAIM_DUPLICATE_THRESHOLD=0.8
CLAIM_AUTO_APPROVE_CAP_AED=10000
```

The webhook receives a JSON POST containing `claim_id`, `broker_id`, `priority`, and `created_at`, with the configured token as a Bearer header. Configure the paging service to authenticate the source and route by `broker_id`. A successful 2xx response confirms delivery to the paging service; it does not confirm the broker has acknowledged the page. If no webhook or active shift exists, the member sees that paging was not confirmed.

A broker starts an eight-hour shift from **Broker → Claim review → Start an 8-hour on-call shift**. Emergency claims during that shift appear in that broker's review queue even when another broker is assigned to the member.

Uploaded JPG, PNG, and PDF files are parsed on the API, including OCR for scanned pages when Tesseract is installed. Only bounded extracted fields and metadata are kept; the original bytes and full extracted text are discarded. This demo does not authenticate source documents or issue real cover.

The `helm_claim_intake_agent` and `helm_claim_risk_agent` database roles have no write grant on `claim_decisions`; `helm_claim_servicing` does. The existing deterministic servicing engine and authenticated broker review remain the only paths that create financial records.
