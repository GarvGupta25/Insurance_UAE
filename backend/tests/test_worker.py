from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import agents, worker
from app.models import Case, Message, Profile, Run


def test_queued_message_completes_and_persists_manual_fallback(fixture_client, monkeypatch):
    _, owners, engine = fixture_client
    owner_id = owners[0].id
    with Session(engine) as db:
        profile = Profile(owner_id=owner_id, facts={}, provenance={})
        case = Case(owner_id=owner_id)
        db.add_all([profile, case])
        db.flush()
        message = Message(
            owner_id=owner_id,
            case_id=case.id,
            role="user",
            text="I need cover.",
            details={"context": {}},
        )
        db.add(message)
        db.flush()
        run = Run(owner_id=owner_id, case_id=case.id, message_id=message.id)
        db.add(run)
        db.commit()
        run_id = run.id
        case_id = case.id

    monkeypatch.setattr(worker, "engine", lambda: engine)
    monkeypatch.setattr(agents, "settings", lambda: SimpleNamespace(groq_api_key=""))
    assert worker.work_once(agents.graph()) is True
    with Session(engine) as db:
        finished = db.get(Run, run_id)
        reply = db.scalar(select(Message).where(Message.role == "assistant", Message.case_id == case_id))
        assert finished.status == "complete"
        assert finished.result["mode"] == "manual"
        assert reply and reply.text
