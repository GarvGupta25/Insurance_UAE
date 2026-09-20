import inspect
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import servicing
from app.models import Base, ClaimDocument, ClaimFlag, ClaimIntake, Policy

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "202609200001_claim_staging.sql"
)


def test_claim_staging_models_enforce_the_phase_one_shape():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            policy = Policy(owner_id="member-a", status="demo_active", snapshot={})
            db.add(policy)
            db.flush()
            intake = ClaimIntake(policy_id=policy.id, kind="claim", structured_fields={"amount": 100})
            db.add(intake)
            db.flush()
            flag = ClaimFlag(
                claim_intake_id=intake.id,
                flag_type="missing_docs",
                reason="Bill date missing.",
            )
            db.add_all(
                (
                    ClaimDocument(claim_intake_id=intake.id, doc_type="bill"),
                    flag,
                )
            )
            db.commit()

            assert set(Base.metadata.tables) >= {"claim_intakes", "claim_documents", "claim_flags"}
            assert flag.status == "open"
            assert ClaimDocument.__table__.c.extracted_fields.nullable is True

            db.add(ClaimIntake(policy_id=policy.id, kind="unsupported"))
            with pytest.raises(IntegrityError):
                db.commit()
    finally:
        engine.dispose()


def test_claim_tables_are_upstream_of_servicing_and_rls_is_scoped():
    source = inspect.getsource(servicing)
    assert all(name not in source for name in ("ClaimIntake", "ClaimDocument", "ClaimFlag", "claim_intakes"))

    migration = MIGRATION.read_text(encoding="utf-8")
    assert migration.count("ENABLE ROW LEVEL SECURITY") == 3
    assert migration.count("public.marketplace_is_broker_or_support()") == 3
    assert migration.count("policy.owner_id = auth.uid()::text") == 3
    assert all(f"GRANT {operation}" not in migration for operation in ("INSERT", "UPDATE", "DELETE"))
