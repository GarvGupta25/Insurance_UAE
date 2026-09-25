from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import BrokerAssignment


def create_case(client):
    return client.post("/api/cases", json={}, headers={"Idempotency-Key": str(uuid4())})


def test_new_intake_clears_returning_regular_member_profile(fixture_client):
    client, _, _ = fixture_client
    assert create_case(client).status_code == 200
    profile = client.get("/api/me/profile").json()
    assert client.patch("/api/me/profile", json={
        "expected_version": profile["version"], "changes": {"legal_name": "Regular Member"}
    }).status_code == 200

    assert create_case(client).status_code == 200
    refreshed = client.get("/api/me/profile").json()
    assert refreshed["facts"] == {}
    assert refreshed["readiness"]["ready"] is False


def test_new_intake_also_clears_broker_linked_regular_member_profile(fixture_client):
    client, owner, engine = fixture_client
    assert create_case(client).status_code == 200
    profile = client.get("/api/me/profile").json()
    assert client.patch("/api/me/profile", json={
        "expected_version": profile["version"], "changes": {"legal_name": "Linked Member"}
    }).status_code == 200
    with Session(engine) as db:
        db.add(BrokerAssignment(member_id=owner[0].id, broker_id=str(uuid4())))
        db.commit()

    assert create_case(client).status_code == 200
    assert client.get("/api/me/profile").json()["facts"] == {}
