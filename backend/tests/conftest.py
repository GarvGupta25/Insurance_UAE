from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import User, current_user
from app.db import session
from app.main import app
from app.models import Base, BrokerAssignment


@contextmanager
def as_assigned_broker(owner, engine):
    member = owner[0]
    with Session(engine) as db:
        assignment = db.get(BrokerAssignment, member.id)
        if assignment is None:
            assignment = BrokerAssignment(member_id=member.id, broker_id=str(uuid4()))
            db.add(assignment)
            db.commit()
        broker = User(assignment.broker_id, "assigned-broker@example.test", "broker")
    owner[0] = broker
    try:
        yield broker
    finally:
        owner[0] = member


@pytest.fixture
def fixture_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    owner = [User(str(uuid4()), "first@example.test")]

    def db():
        with Session(engine) as value:
            yield value

    app.dependency_overrides[session] = db
    app.dependency_overrides[current_user] = lambda: owner[0]
    with TestClient(app) as client:
        yield client, owner, engine
    app.dependency_overrides.clear()
    engine.dispose()
