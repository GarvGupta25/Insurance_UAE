# Marketplace Pivot v2 — Phase 8 final status

Date: 20 September 2026  
Pivot baseline: `ebd3745`  
Verified source state before Phase 8: `6141cd3`

## Result

The source boundary, clean-database marketplace journey, backend regression suite, frontend type check,
production build, and browser suite all pass. The launcher now idempotently seeds the marketplace
catalogue and all four provider demo logins before starting the application.

The required Docker/Supabase launcher rerun could not be executed on this host: Docker/Podman and WSL
are not installed and `backend/.env` does not exist. This is an environment prerequisite failure, not a
test failure. The exact live rerun remains the only unchecked item below; no live result is claimed.

## Boundary check

Each protected path was compared directly between `ebd3745` and `6141cd3` with Git object hashes.

| Protected scope | Baseline blob | Verified blob | Result |
| --- | --- | --- | --- |
| `frontend/src/marketing/components/ChatPanel.tsx` | `2191b8fd4d6d9ffaada1a12667fc7a51f608c8dc` | same | Unchanged |
| `frontend/src/marketing/components/ChatbotLauncher.tsx` | `adb38a4412450a5b8d5de7120d29e86bb2169440` | same | Unchanged |
| `backend/app/public_assistant.py` | `4e4c93ccfbe4ec0cbfc8f801353ebaeb6e4c8ca4` | same | Unchanged |
| `backend/app/domain.py` | `405fef374cd53b761085813a7f46639da942072a` | same | Unchanged |
| `backend/app/servicing.py` | `c77bb08ea2edcdda62a899ca183cb457bf32acf5` | same | Unchanged |
| `backend/data/hackathon_data.json` | `ea89790288b03e6ee665921d8771590db6b8e46b` | same | Unchanged |

`backend/app/staff.py` does not exist at either the baseline or verified revision, so there is no
pre-existing escalation implementation at that path to alter. The entire Helm Direct fixture is
byte-identical, which is stricter than allowing only a new `provider_id` field on its three plans.

## Fresh-database end-to-end evidence

`backend/tests/test_marketplace_full_journey.py` creates a new empty relational database, loads the
deterministic 30-plan seed catalogue, and performs the journey through the real FastAPI routes and ORM
models. It does not mock marketplace responses.

1. A new, complete synthetic member profile and assigned broker are created.
2. A persisted Checkpoint 1 approval is created and the catalogue endpoint returns exactly five ranked
   plans plus the explicit consent question.
3. Literal `yes` consent creates one application per distinct recommended provider.
4. Every seeded provider identity is checked: invited providers see only their own application and the
   non-invited provider sees an empty inbox.
5. Every invited provider submits a complete quotation; the member endpoint returns a ready, ranked
   top-three comparison based on those submitted premiums and terms.
6. The member selects the first ranked quotation. All alternatives become declined.
7. Only the selected provider can accept. Starting a policy before Checkpoint 2 returns `403`.
8. The assigned broker approves Checkpoint 2, after which only the selected provider can start the
   policy.
9. The bound policy is visible to the member, selected provider, and assigned broker. It is absent for
   every other seeded provider and an unrelated member; direct cross-tenant access returns `404`.

The intake invariant is independently covered by
`test_full_linear_intake_answers_every_applicable_field_once`: all applicable questions occur exactly
once, in order, with no repeats or skipped fields. Resume and clarification paths are also covered.

## Final verification output

Executed from a clean working tree plus the Phase 8 changes:

```text
python -m pytest backend/tests -q
90 passed in 15.82s

python -m ruff check backend/app backend/tests backend/scripts
All checks passed!

npm run check
tsc -b (exit 0)

npm run build
1832 modules transformed
production build completed in 16.80s (exit 0)

npm run test:e2e
5 passed (36.2s)
```

Vite reports its existing advisory that the main minified chunk is larger than 500 kB. It does not fail
the build.

## Launcher and remaining live check

`scripts/start-prototype.ps1` now runs `seed_marketplace_providers.py` immediately after the standard
demo-account bootstrap and points operators to `SEED_PROVIDER_LOGINS.md`. This makes the seeded provider
accounts available after a normal project launch instead of requiring an undocumented manual seed.

Live preflight evidence on this host:

```text
docker: command not found
podman: not installed
WSL: not installed
backend/.env: missing
```

After installing the documented prerequisites, the remaining acceptance command is:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-prototype.ps1
```

Then repeat the nine-stage journey above with the member, broker, and provider accounts printed by the
launcher/recorded in `SEED_PROVIDER_LOGINS.md`.

## Phase 8 checklist

- [x] Zero diff on every out-of-scope file; Helm Direct fixture is byte-identical.
- [x] Full clean-database marketplace journey passes with the deterministic seeded catalogue and real
  application/quotation/policy persistence.
- [x] Full backend, frontend, lint, build, and browser suites are green.
- [x] Existing launcher automatically provisions marketplace providers and provider logins.
- [ ] Launcher restart and live Supabase walkthrough — blocked only by the missing host prerequisites
  listed above.
