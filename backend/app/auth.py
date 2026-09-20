from dataclasses import dataclass
from typing import Literal

import httpx
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .db import session
from .marketplace_models import ProviderUser


@dataclass(frozen=True)
class User:
    id: str
    email: str
    role: Literal["member", "broker", "provider"] = "member"


@dataclass(frozen=True)
class ProviderIdentity:
    user_id: str
    email: str
    provider_id: str
    display_name: str


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
    claimed_role = body.get("app_metadata", {}).get("helm_role")
    role = claimed_role if claimed_role in ("broker", "provider") else "member"
    return User(id=body["id"], email=body.get("email", ""), role=role)


def require_broker(user: User = Depends(current_user)) -> User:
    if user.role != "broker":
        raise HTTPException(403, "A broker account is required for this review.")
    return user


def require_provider(
    user: User = Depends(current_user), db: Session = Depends(session)
) -> ProviderIdentity:
    if user.role != "provider":
        raise HTTPException(403, "A provider account is required for this workspace.")
    mapping = db.get(ProviderUser, user.id)
    if mapping is None:
        raise HTTPException(403, "This account is not assigned to a provider.")
    return ProviderIdentity(user.id, user.email, mapping.provider_id, mapping.display_name)
