"""Create the fixed local-only Helm demonstration accounts."""

import sys
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import engine


PASSWORD = "password"
ACCOUNTS = {
    "member@example": "member",
    "broker@example": "broker",
    "regular@example": "member",
}


def main() -> None:
    cfg = settings()
    if not cfg.supabase_anon_key:
        raise SystemExit("Local Supabase configuration is missing.")

    with httpx.Client(timeout=15) as client, engine().begin() as db:
        ids: dict[str, str] = {}
        for email in ACCOUNTS:
            existing = db.execute(
                text("SELECT id::text FROM auth.users WHERE email = :email"), {"email": email}
            ).scalar_one_or_none()
            if existing:
                ids[email] = existing
                continue

            response = client.post(
                cfg.supabase_url.rstrip("/") + "/auth/v1/signup",
                headers={"apikey": cfg.supabase_anon_key, "Content-Type": "application/json"},
                json={"email": email, "password": PASSWORD},
            )
            response.raise_for_status()
            ids[email] = response.json()["user"]["id"]

        for account_id in ids.values():
            db.execute(
                text(
                    "UPDATE auth.users "
                    "SET encrypted_password = crypt(:password, gen_salt('bf')), "
                    "email_confirmed_at = COALESCE(email_confirmed_at, now()), updated_at = now() "
                    "WHERE id = CAST(:id AS uuid)"
                ),
                {"id": account_id, "password": PASSWORD},
            )

        db.execute(
            text(
                "UPDATE auth.users "
                "SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) - 'helm_role' "
                "WHERE id IN (CAST(:member AS uuid), CAST(:regular AS uuid))"
            ),
            {"member": ids["member@example"], "regular": ids["regular@example"]},
        )
        db.execute(
            text(
                "UPDATE auth.users "
                "SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) "
                "|| '{\"helm_role\":\"broker\"}'::jsonb "
                "WHERE id = CAST(:broker AS uuid)"
            ),
            {"broker": ids["broker@example"]},
        )
        db.execute(
            text("DELETE FROM public.broker_assignments WHERE member_id = :member"),
            {"member": ids["member@example"]},
        )
        db.execute(
            text(
                "INSERT INTO public.broker_assignments (member_id, broker_id) "
                "VALUES (:member, :broker)"
            ),
            {"member": ids["member@example"], "broker": ids["broker@example"]},
        )

    print("Local Helm demonstration accounts are ready.")


if __name__ == "__main__":
    main()
