"""Durable, bounded agent jobs. Run separately: python -m app.worker."""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .agents import graph
from .config import settings
from .db import engine
from .models import Message, Profile, Run


def work_once(compiled):
    now = datetime.now(timezone.utc)
    with Session(engine()) as db:
        run = db.scalar(
            select(Run)
            .where(or_(Run.status == "queued", (Run.status == "running") & (Run.leased_until < now)))
            .order_by(Run.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not run:
            return False
        if run.attempts >= 2:
            run.status = "failed"
            run.result = {
                "reply": "This request could not finish. Your saved profile is safe; retry or edit it directly.",
                "patch": {},
                "mode": "error",
            }
            db.commit()
            return True
        run.status, run.attempts = "running", run.attempts + 1
        run.leased_until = now + timedelta(seconds=90)
        message = db.get(Message, run.message_id)
        profile = db.scalar(select(Profile).where(Profile.owner_id == run.owner_id))
        facts = {k: v for k, v in profile.facts.items() if k not in {"passport_number", "emirates_id"}}
        recent_messages = list(
            reversed(
                db.scalars(
                    select(Message)
                    .where(Message.case_id == run.case_id, Message.id != message.id)
                    .order_by(Message.created_at.desc())
                    .limit(8)
                ).all()
            )
        )
        run_id, owner_id, case_id, message_id, version = (
            run.id,
            run.owner_id,
            run.case_id,
            message.id,
            profile.version,
        )
        state = {
            "text": message.text,
            "facts": facts,
            "message_id": message.id,
            "context": {
                **message.details.get("context", {}),
                "conversation": [{"role": item.role, "text": item.text} for item in recent_messages],
            },
        }
        db.commit()
    try:
        output = compiled.invoke(
            state, {"configurable": {"thread_id": f"{owner_id}:{case_id}"}, "recursion_limit": 64}
        )["result"]
        status = "complete"
    except Exception:
        # Never log prompts, health facts, API responses or secrets.
        output = {
            "reply": "The assistant could not finish this request. Please retry, or use the editable profile.",
            "patch": {},
            "mode": "error",
            "sources": [],
        }
        status = "failed"
    with Session(engine()) as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run.status != "running":
            return True
        output.update({"source_message_id": message_id, "profile_version": version})
        run.result, run.status = output, status
        db.add(
            Message(
                owner_id=owner_id, case_id=case_id, role="assistant", text=output["reply"], details=output
            )
        )
        db.commit()
    return True


def main():
    uri = settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(uri) as saver:
        saver.setup()
        # Checkpoints can contain health context; never expose them through Supabase's browser API.
        import psycopg

        with psycopg.connect(uri, autocommit=True) as connection:
            for table in ("checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                connection.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
                connection.execute(f"REVOKE ALL ON public.{table} FROM anon, authenticated")
        compiled = graph(saver)
        while True:
            if not work_once(compiled):
                time.sleep(1)


if __name__ == "__main__":
    main()
