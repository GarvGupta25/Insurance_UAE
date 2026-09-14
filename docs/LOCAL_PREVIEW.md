# Run the feature-branch prototype without Supabase

This local preview runs the real FastAPI routes, worker, React app and fictional plan catalogue against an ignored SQLite database. It is intended for a single person trying the `codex/agentic-onboarding-finance` branch on their own computer. It binds the API to `127.0.0.1` and deliberately substitutes two synthetic accounts for Supabase authentication. Never deploy `scripts/preview_server.py` or expose its port to a network.

From the repository root, install backend and frontend dependencies if needed. The normal project requirements are Python 3.12 and Node 22+; the preview does not require Docker, Supabase, Groq or payment credentials.

```powershell
cd backend
uv sync --python 3.12
```

```powershell
cd frontend
npm install
```

Start the API in one terminal from `backend/`:

```powershell
uv run python scripts/preview_server.py
```

Start the web app in another terminal from `frontend/`:

```powershell
$env:VITE_LOCAL_PREVIEW='1'
npm run dev -- --port 5173
```

Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/). Choose **Find my cover** to enter the synthetic member workspace. Start a case, answer the guided questions or edit the profile, review and accept each proposed detail, then get a quotation. The quote page includes ranking, PDF download, financial scenario sliders and financial-planning chat. Prepare an application, use **Switch to broker demo** in the sidebar to approve its recommendation, then switch back to the member to confirm and explore the sandbox policy and payments.

The two demo roles share the local database at `.runtime/preview.db`, which is ignored by Git. The member role is already assigned to the broker role. To start over, stop the API, remove that one file, then restart it. Do not enter real identity, medical, payment or insurer data: this mode bypasses authentication and uses fictional insurance terms. Its guided chat is deterministic without Groq; voice and real insurer/payment integrations are unavailable. The standard Supabase-backed launch remains in the main README.
