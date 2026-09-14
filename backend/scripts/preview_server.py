"""Loopback-only, synthetic prototype using the real API and a local SQLite database.

Run with the bundled environment's Python. This server deliberately bypasses Supabase
authentication and must never be deployed or bound to a public interface.
"""

import os
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import Header
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ["GROQ_API_KEY"] = ""  # The local prototype uses guided, deterministic chat.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db, worker  # noqa: E402
from app.agents import graph  # noqa: E402
from app.auth import User, current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, BrokerAssignment  # noqa: E402

MEMBER_ID = "10000000-0000-4000-8000-000000000001"
BROKER_ID = "10000000-0000-4000-8000-000000000002"
SMOKE_ID = "10000000-0000-4000-8000-000000000003"
PREVIEW_DB = Path(__file__).resolve().parents[2] / ".runtime" / "preview.db"


def preview_user(x_preview_role: str = Header(default="member")) -> User:
    if x_preview_role == "broker":
        return User(BROKER_ID, "demo-broker@helm.local", "broker")
    if x_preview_role == "smoke":
        return User(SMOKE_ID, "preview-smoke@helm.local")
    return User(MEMBER_ID, "demo-member@helm.local")


def run_jobs():
    compiled = graph()
    while True:
        try:
            if not worker.work_once(compiled):
                time.sleep(0.5)
        except Exception as exc:
            # Never print profile details or message text to the preview console.
            print(f"Preview agent job paused ({type(exc).__name__}); retrying.", flush=True)
            time.sleep(2)


def main():
    PREVIEW_DB.parent.mkdir(parents=True, exist_ok=True)
    database = create_engine(f"sqlite+pysqlite:///{PREVIEW_DB.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(database)
    with Session(database) as session:
        if session.get(BrokerAssignment, MEMBER_ID) is None:
            session.add(BrokerAssignment(member_id=MEMBER_ID, broker_id=BROKER_ID))
            session.commit()
    db.engine = lambda: database
    worker.engine = lambda: database
    app.dependency_overrides[current_user] = preview_user
    threading.Thread(target=run_jobs, name="helm-preview-agent", daemon=True).start()
    print("Synthetic preview API ready on http://127.0.0.1:8000", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
