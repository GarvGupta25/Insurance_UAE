"""Exercise member, assigned broker and policy servicing against local Supabase."""

import secrets
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import engine


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
    suffix = uuid4().hex[:12]
    member_email = f"helm-member-{suffix}@example.test"
    broker_email = f"helm-broker-{suffix}@example.test"
    password = "LocalOnly-" + secrets.token_urlsafe(16)
    with httpx.Client(timeout=20) as client:
        auth_headers = {"apikey": cfg.supabase_anon_key, "Content-Type": "application/json"}

        def create_account(email):
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
            return signup.json()["user"]["id"], login.json()["access_token"]

        member_id, token = create_account(member_email)
        broker_id, _ = create_account(broker_email)
        with engine().begin() as db:
            db.execute(
                text("UPDATE auth.users SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || '{\"helm_role\":\"broker\"}'::jsonb WHERE id = CAST(:id AS uuid)"),
                {"id": broker_id},
            )
            db.execute(
                text("INSERT INTO public.broker_assignments (member_id, broker_id) VALUES (CAST(:member AS uuid), CAST(:broker AS uuid))"),
                {"member": member_id, "broker": broker_id},
            )
        broker_login = client.post(
            cfg.supabase_url + "/auth/v1/token?grant_type=password",
            headers=auth_headers,
            json={"email": broker_email, "password": password},
        )
        broker_login.raise_for_status()
        broker_token = broker_login.json()["access_token"]
        api = "http://127.0.0.1:8000/api"
        assert request(client, "GET", api + "/me/access", token)["role"] == "member"
        assert request(client, "GET", api + "/me/access", broker_token)["role"] == "broker"
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
        denied = client.post(
            f"{api}/applications/{app}/submit",
            headers={"apikey": cfg.supabase_anon_key, "Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())},
            json={"payload_hash": preview["payload_hash"], "declarations_confirmed": True},
        )
        assert denied.status_code == 409, denied.text
        queue = request(client, "GET", api + "/broker/recommendations", broker_token)
        recommendation_id = preview["recommendation_id"]
        assert any(item["id"] == recommendation_id for item in queue)
        request(
            client,
            "POST",
            f"{api}/broker/recommendations/{recommendation_id}/review",
            broker_token,
            {"action": "approve", "note": "Local synthetic smoke review."},
        )
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
        operation = {
            "event_id": "SMOKE-CLM-1",
            "kind": "claim",
            "policy_month": 0,
            "benefit_class": "general",
            "provider_tier": "in_network_clinic",
            "billed_amount": 3200,
        }
        servicing_preview = request(client, "POST", f"{api}/policies/{policy}/servicing/preview", token, operation)
        assert servicing_preview["decision"]["plan_pays_fils"] == 119000
        servicing = request(
            client,
            "POST",
            f"{api}/policies/{policy}/servicing",
            token,
            {**operation, "expected_policy_version": servicing_preview["policy_version"]},
        )
        assert servicing["decision"]["plan_pays_fils"] == 119000
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
        "Local authenticated smoke test passed: member, assigned broker, quote, approval, policy, claim and sandbox receipt."
    )


if __name__ == "__main__":
    main()
