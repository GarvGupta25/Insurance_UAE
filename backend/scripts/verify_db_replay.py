"""Delete and rebuild every derived ledger projection, asserting no ledger drift."""

from sqlalchemy import select

from app.db import session
from app.models import LedgerProjection, Policy
from app.servicing import rebuild_projection


def main():
    with next(session()) as db:
        policies = db.scalars(select(Policy)).all()
        before = {row.policy_id: row.ledger for row in db.scalars(select(LedgerProjection)).all()}
        db.query(LedgerProjection).delete()
        db.flush()
        rebuilt = {}
        for policy in policies:
            ledger, _ = rebuild_projection(db, policy)
            rebuilt[policy.id] = ledger
        for policy_id, ledger in before.items():
            assert rebuilt.get(policy_id) == ledger, f"Projection drift for policy {policy_id}"
        db.rollback()
    print(f"Database replay verification passed for {len(policies)} policy projection(s).")


if __name__ == "__main__":
    main()
