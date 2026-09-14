# Integrated implementation status

Current authority: the user's combined Version 2/Version 3 workflow, restricted to the supplied fictional catalogue and saved demo inputs. This proposed extension lives on `codex/agentic-onboarding-finance` pending review; `main` retains the previous baseline.

| Workflow gate | Status |
| --- | --- |
| Supabase-ready account ownership and returning users | Complete locally |
| Three-stage conversational and editable profile intake | Complete |
| Identity extraction with review/manual fallback | Complete |
| Supplied fictional catalogue, comparison and quotation PDF | Complete |
| Easy Fill, mandatory broker review and member confirmation | Complete |
| Sandbox policy, payment receipt, portfolio and fictional provider map | Complete |
| Pre-authorisation, claim and reimbursement evaluation | Complete |
| Append-only servicing history and rebuildable ledger | Complete |
| Member appeal, broker uphold/overturn and effective replay | Complete |
| History-aware reassessment and broker retain/future recommendation | Complete |
| Durable case-level conversational context | Complete |
| Guided offline intake through a reviewed fact and automatic indicative quote | Complete on proposed branch |
| Conversational and drag-to-explore financial planning over the fictional quote | Complete on proposed branch |
| Backend validation | 56 tests and Ruff pass on proposed branch |
| Frontend validation | TypeScript check, production build and 3 browser tests pass on proposed branch |

The first four implementation gates are verified in [PHASE_1_4_ACCEPTANCE.md](PHASE_1_4_ACCEPTANCE.md). Broker reviews require a separate administrator-designated broker account and an assignment to the member. Provisioning instructions are in [BROKER_SETUP.md](BROKER_SETUP.md); the local Supabase migrations and a two-account quote → approval → policy → claim → appeal replay walkthrough now pass. The workflow never uses live insurer, provider, underwriting, payment, or product data: plans, providers, cover, payments and recommendations remain fictional demonstrations. Optional Groq and Razorpay test paths need local keys to run; they are not required for the supplied-data workflow.

The financial-scenario migration on the proposed branch has SQLite/API coverage but could not be applied to local Supabase in this environment because Docker or Podman is unavailable. See [AGENTIC_SHOPPING_FINANCE.md](AGENTIC_SHOPPING_FINANCE.md) for the source-backed presentation requirements and model assumptions.
