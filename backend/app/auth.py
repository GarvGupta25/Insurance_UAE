from dataclasses import dataclass
from typing import Literal

import httpx
from fastapi import Depends, Header, HTTPException

from .config import settings


@dataclass(frozen=True)
class User:
    id: str
    email: str
    role: Literal["member", "broker"] = "member"


def current_user(authorization: str = Header(default="")) -> User:
    config = settings()
    if not config.supabase_anon_key:
        raise HTTPException(503, "Configure Supabase to sign in. No account or session has been simulated.")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in.")
    # Supabase Auth validates token signature, issuer, expiry and active user; never trust decoded client claims.
    try:
        response = httpx.get(
            config.supabase_url.rstrip("/") + "/auth/v1/user",
            headers={
                "apikey": config.supabase_anon_key,
                "Authorization": authorization,
            },
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Sign-in service is temporarily unavailable.") from None
    if response.status_code != 200:
        raise HTTPException(401, "Your session expired. Please sign in again.")
    body = response.json()
    # app_metadata is controlled by Supabase administrators; user_metadata is not.
    role = "broker" if body.get("app_metadata", {}).get("helm_role") == "broker" else "member"
    return User(id=body["id"], email=body.get("email", ""), role=role)


def require_broker(user: User = Depends(current_user)) -> User:
    if user.role != "broker":
        raise HTTPException(403, "A broker account is required for this review.")
    return user
