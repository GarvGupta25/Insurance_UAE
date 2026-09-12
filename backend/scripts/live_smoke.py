"""Exercise the local Supabase-authenticated Phase 1 path without printing secrets."""

import sys
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings


def request(client, method, path, token=None, body=None):
    headers = {"apikey": settings().supabase_anon_key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if method == "POST":
        headers["Idempotency-Key"] = str(uuid4())
    response = client.request(method, path, headers=headers, json=body)
    response.raise_for_status()
    return response.json()


def main():
    cfg = settings()
    if not cfg.supabase_anon_key:
        raise SystemExit("Local Supabase configuration is missing.")
    email = f"phase-one-{uuid4().hex[:12]}@example.test"
    password = "LocalOnlyPass-987!"
    with httpx.Client(timeout=20) as client:
        auth_headers = {"apikey": cfg.supabase_anon_key, "Content-Type": "application/json"}
        signup = client.post(
            cfg.supabase_url + "/auth/v1/signup",
            headers=auth_headers,
            json={"email": email, "password": password},
        )
        signup.raise_for_status()
        login = client.post(
            cfg.supabase_url + "/auth/v1/token?grant_type=password",
            headers=auth_headers,
            json={"email": email, "password": password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        api = "http://127.0.0.1:8000/api"
        initial = request(client, "GET", api + "/me/profile", token)
        profile = request(
            client,
            "PATCH",
            api + "/me/profile",
            token,
            {
                "expected_version": initial["version"],
                "changes": {
                    "legal_name": "Local Demo Applicant",
                    "date_of_birth": "1994-03-12",
                    "nationality": "Indian",
                    "residency": "resident",
                    "emirate": "Dubai",
                    "diagnosed_conditions": "no",
                    "conditions": [],
                    "smoker": "no",
                    "maternity": False,
                    "geography": "UAE",
                    "start_date": (date.today() + timedelta(days=1)).isoformat(),
                    "payer": "self",
                    "annual_budget": 12000,
                    "strict_budget": False,
                    "payment_frequency": "monthly",
                },
            },
        )
        assert profile["readiness"]["ready"]
        case = request(client, "POST", api + "/cases", token)["id"]
        message = request(
            client,
            "POST",
            f"{api}/cases/{case}/messages",
            token,
            {"text": "I need basic cover and prefer a lower premium.", "modality": "text"},
        )
        run = None
        for _ in range(12):
            run = request(client, "GET", f"{api}/runs/{message['run_id']}", token)
            if run["status"] in {"complete", "failed"}:
                break
            time.sleep(1)
        assert run and run["status"] == "complete", run
        assert run["result"]["mode"] in {"manual", "groq"}
        quote = request(client, "POST", f"{api}/cases/{case}/quotes", token)["id"]
        quoted = request(client, "GET", f"{api}/quotes/{quote}", token)
        assert quoted["recommended_plan_id"] == "plan_a"
        app = request(
            client, "POST", api + "/applications/prepare", token, {"quote_id": quote, "plan_id": "plan_a"}
        )["id"]
        preview = request(client, "GET", f"{api}/applications/{app}", token)
        policy = request(
            client,
            "POST",
            f"{api}/applications/{app}/submit",
            token,
            {"payload_hash": preview["payload_hash"], "declarations_confirmed": True},
        )["policy_id"]
        policy_view = request(client, "GET", f"{api}/policies/{policy}", token)
        assert policy_view["status"] == "demo_active" and len(policy_view["instalments"]) == 12
        order = request(
            client, "POST", f"{api}/instalments/{policy_view['instalments'][0]['id']}/payment-order", token
        )
        settlement = request(
            client, "POST", f"{api}/payment-orders/{order['id']}/simulate", token, {"result": "captured"}
        )
        assert settlement["status"] == "captured"
        final = request(client, "GET", f"{api}/policies/{policy}", token)
        assert final["paid_fils"] == final["instalments"][0]["amount"]
    print(
        "Local authenticated Phase 1 smoke test passed: profile, quote, application, policy and sandbox receipt."
    )


if __name__ == "__main__":
    main()
