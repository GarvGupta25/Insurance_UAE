from uuid import uuid4

import pytest
from conftest import as_assigned_broker
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth import User
from app.models import Base, BrokerAssignment, Recommendation
from app.services import assigned


def test_only_the_assigned_broker_can_open_a_member_recommendation():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    member_id, broker_id = str(uuid4()), str(uuid4())
    with Session(engine) as db:
        recommendation = Recommendation(
            owner_id=member_id, case_id=str(uuid4()), quote_id=str(uuid4()),
            profile_version=1, proposed_plan_id="plan_a", certainty="clear", summary={},
        )
        db.add(recommendation)
        db.add(BrokerAssignment(member_id=member_id, broker_id=broker_id))
        db.commit()
        assert assigned(db, Recommendation, recommendation.id, User(broker_id, "broker@test.local", "broker")) == recommendation
        with pytest.raises(HTTPException) as member_error:
            assigned(db, Recommendation, recommendation.id, User(member_id, "member@test.local"))
        assert member_error.value.status_code == 403
        with pytest.raises(HTTPException) as other_error:
            assigned(db, Recommendation, recommendation.id, User(str(uuid4()), "other@test.local", "broker"))
        assert other_error.value.status_code == 404
    engine.dispose()


def test_broker_queue_and_review_are_hidden_from_members_and_unassigned_brokers(fixture_client):
    client, owner, engine = fixture_client
    facts = {
        "age": 26, "marital_status": "single", "smoker": "no",
        "diagnosed_conditions": "no", "budget_category": "low", "priorities": ["lowest premium"],
    }
    current = client.get("/api/me/profile").json()
    assert client.patch("/api/me/profile", json={"expected_version": current["version"], "changes": facts}).status_code == 200
    def send(path, body=None):
        return client.post(path, json=body or {}, headers={"Idempotency-Key": str(uuid4())})
    case = send("/api/cases").json()["id"]
    quote = send(f"/api/cases/{case}/quotes").json()["id"]
    application = send("/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a", "request_broker_review": True}).json()["id"]
    recommendation_id = client.get(f"/api/applications/{application}").json()["recommendation_id"]
    assert client.get("/api/me/access").json() == {"role": "member"}
    assert client.get("/api/broker/recommendations").status_code == 403
    assert send(f"/api/broker/recommendations/{recommendation_id}/review", {"action": "approve"}).status_code == 403
    member = owner[0]
    owner[0] = User(str(uuid4()), "unassigned@test.local", "broker")
    assert client.get("/api/broker/recommendations").json() == []
    assert send(f"/api/broker/recommendations/{recommendation_id}/review", {"action": "approve"}).status_code == 404
    owner[0] = member
    with as_assigned_broker(owner, engine):
        assert client.get("/api/me/access").json() == {"role": "broker"}
        assert [item["id"] for item in client.get("/api/broker/recommendations").json()] == [recommendation_id]
        assert send(f"/api/broker/recommendations/{recommendation_id}/review", {"action": "approve"}).status_code == 200


def test_broker_cannot_approve_a_recommendation_after_profile_change(fixture_client):
    client, owner, engine = fixture_client
    facts = {"age": 26, "marital_status": "single", "smoker": "no", "diagnosed_conditions": "no", "budget_category": "low", "priorities": ["lowest premium"]}
    current = client.get("/api/me/profile").json()
    assert client.patch("/api/me/profile", json={"expected_version": current["version"], "changes": facts}).status_code == 200
    def send(path, body=None):
        return client.post(path, json=body or {}, headers={"Idempotency-Key": str(uuid4())})
    case = send("/api/cases").json()["id"]
    quote = send(f"/api/cases/{case}/quotes").json()["id"]
    application = send("/api/applications/prepare", {"quote_id": quote, "plan_id": "plan_a"}).json()["id"]
    recommendation_id = client.get(f"/api/applications/{application}").json()["recommendation_id"]
    changed = client.get("/api/me/profile").json()
    assert client.patch("/api/me/profile", json={"expected_version": changed["version"], "changes": {"priorities": ["good network access"]}}).status_code == 200
    with as_assigned_broker(owner, engine):
        response = send(f"/api/broker/recommendations/{recommendation_id}/review", {"action": "approve"})
        assert response.status_code == 409
