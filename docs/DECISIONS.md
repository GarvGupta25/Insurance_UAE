# Implementation decisions

## Agent boundary

Groq/LangGraph may interpret a message into a proposed typed patch and write a short grounded explanation. The deterministic service owns plan comparison, premiums, monetary schedules, application mapping, confirmation validity, policy snapshots and payment settlement. The model cannot make a purchase, issue cover, decide underwriting or accept declarations.

## Voice boundary

The browser records a short user-triggered clip using a supported `MediaRecorder` format. The API decodes the bounded audio before sending it to Groq, returns an editable transcript and does not store audio. Sending the transcript creates an ordinary case message; material extracted facts still need the profile review step. Voice cannot submit an application or a payment. Read-aloud speaks only already-authorized screen text and stops before a new recording begins.

## Ownership and access

The backend verifies the Supabase access token against `/auth/v1/user`, resolves the owner from that response and performs every lookup through an owner constraint. Browser database access is read-only and RLS-protected; write paths stay server-side. Documents, agent runs, command receipts and audit records are not browser-readable.

## Payments

`simulator` is the default and visibly local. The Razorpay adapter only accepts a test key, validates an order against the saved amount/currency and verifies server-side state before it settles a receipt. Browser checkout success alone is not enough. Webhooks verify raw-body signatures and re-fetch provider state.

## Local Supabase note

The npm CLI version pinned in this workspace occasionally emits a missing local profile warning on Windows. The documented `--ignore-health-check` start path brings up the required database, Auth, REST and Kong services; the database reset applies project migrations. The repository never commits local `.env` files or generated keys.
