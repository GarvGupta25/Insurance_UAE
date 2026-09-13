from sqlalchemy import func, select

from .domain import empty_ledger, evaluate_servicing
from .models import LedgerProjection, ServicingEvent


def _projection(db, policy):
    projection = db.scalar(
        select(LedgerProjection).where(LedgerProjection.policy_id == policy.id).with_for_update()
    )
    if projection is None:
        projection = LedgerProjection(owner_id=policy.owner_id, policy_id=policy.id, ledger=empty_ledger())
        db.add(projection)
        db.flush()
    return projection


def _next_sequence(db, policy_id):
    return (db.scalar(select(func.max(ServicingEvent.sequence)).where(ServicingEvent.policy_id == policy_id)) or 0) + 1


def present_event(record):
    return {
        "id": record.id,
        "event_id": record.root_id,
        "record_type": record.record_type,
        "kind": record.kind,
        "policy_month": record.effective_month,
        "outcome": record.outcome,
        "reason_code": record.reason_code,
        "plan_pays_fils": record.plan_pays_fils,
        "member_pays_fils": record.member_pays_fils,
        "calculation": record.calculation,
        "ledger_before": record.ledger_before,
        "ledger_after": record.ledger_after,
        "supersedes_id": record.supersedes_id,
        "reviewer_action": record.reviewer_action,
        "recorded_at": record.created_at.isoformat(),
    }


def rebuild_projection(db, policy):
    """Replay current effective financial decisions without modifying the audit trail."""
    projection = _projection(db, policy)
    rows = db.scalars(
        select(ServicingEvent)
        .where(
            ServicingEvent.policy_id == policy.id,
            ServicingEvent.record_type.in_(["decision", "revision"]),
        )
        .order_by(ServicingEvent.sequence)
    ).all()
    latest_by_root = {}
    original_sequence = {}
    for row in rows:
        latest_by_root[row.root_id] = row
        original_sequence.setdefault(row.root_id, row.sequence)
    effective = sorted(
        latest_by_root.values(),
        key=lambda row: (row.effective_month if row.effective_month is not None else 1201, original_sequence[row.root_id]),
    )
    ledger, decisions = empty_ledger(), {}
    for row in effective:
        decision = evaluate_servicing(policy.snapshot["plan"], row.payload, ledger)
        decisions[row.root_id] = decision
        if row.kind != "preauth" and decision["outcome"] == "covered":
            ledger = decision["ledger_after"]
    projection.ledger = ledger
    projection.through_sequence = max((row.sequence for row in rows), default=0)
    return ledger, decisions


def record_financial_event(db, policy, request):
    """Persist one idempotent deterministic decision and refresh the derived projection."""
    existing = db.scalar(
        select(ServicingEvent).where(
            ServicingEvent.policy_id == policy.id,
            ServicingEvent.root_id == request["id"],
            ServicingEvent.record_type == "decision",
        )
    )
    if existing:
        return present_event(existing), _projection(db, policy).ledger
    projection = _projection(db, policy)
    decision = evaluate_servicing(policy.snapshot["plan"], request, projection.ledger)
    record = ServicingEvent(
        owner_id=policy.owner_id,
        policy_id=policy.id,
        root_id=request["id"],
        record_type="decision",
        kind=request["kind"],
        effective_month=request.get("policy_month"),
        sequence=_next_sequence(db, policy.id),
        payload=request,
        outcome=decision["outcome"],
        reason_code=decision["reason_code"],
        plan_pays_fils=decision["plan_pays_fils"],
        member_pays_fils=decision["member_pays_fils"],
        calculation=decision["calculation"],
        ledger_before=decision["ledger_before"],
        ledger_after=decision["ledger_after"],
    )
    db.add(record)
    db.flush()
    ledger, _ = rebuild_projection(db, policy)
    if request["kind"] != "preauth" and decision["outcome"] == "covered":
        policy.version += 1
    return present_event(record), ledger
