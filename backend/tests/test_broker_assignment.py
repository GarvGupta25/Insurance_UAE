from uuid import uuid4

import pytest
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
