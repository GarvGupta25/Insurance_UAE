from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import auth


@pytest.mark.parametrize(
    ("app_role", "user_role", "expected"),
    [(None, "broker", "member"), ("broker", None, "broker"), ("member", "broker", "member")],
)
def test_only_administrator_controlled_metadata_grants_broker_role(monkeypatch, app_role, user_role, expected):
    monkeypatch.setattr(auth, "settings", lambda: SimpleNamespace(supabase_anon_key="test", supabase_url="http://local"))
    monkeypatch.setattr(auth.httpx, "get", lambda *_args, **_kwargs: SimpleNamespace(
        status_code=200,
        json=lambda: {"id": "verified-user", "email": "example@test.local", "app_metadata": {"helm_role": app_role}, "user_metadata": {"helm_role": user_role}},
    ))
    user = auth.current_user("Bearer verified-token")
    assert user.role == expected
    if expected == "member":
        with pytest.raises(HTTPException) as error:
            auth.require_broker(user)
        assert error.value.status_code == 403
    else:
        assert auth.require_broker(user) == user
