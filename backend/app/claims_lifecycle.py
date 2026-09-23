"""Deterministic claim authority and broker-only quality controls."""

from datetime import datetime, timezone
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select

from .claims_phase_one import log
from .models import ClaimAutoRule, ClaimDecision, ClaimIntake, ClaimQualityAudit, LedgerProjection, Policy, ProvisionalAuthRule


def provisional(db, intake, policy, category: str) -> ClaimDecision | None:
    plan = policy.snapshot.get("plan", {})
    rule = db.scalar(select(ProvisionalAuthRule).where(
        ProvisionalAuthRule.policy_type == plan.get("id"),
        ProvisionalAuthRule.claim_category == category,
        ProvisionalAuthRule.active.is_(True),
    ))
    checks = {"emergency_flag": intake.is_emergency, "active_policy": policy.status == "demo_active",
              "covered_category": category == "emergency_room_admission" and plan.get("annual_limit", 0) > 0}
    if not rule or not all(checks.values()) or not all(checks.get(condition, False) for condition in rule.requires_conditions):
        log(db, intake.id, "system", "provisional_engine", "provisional_not_issued",
            {"category": category, "checks": checks, "rule_id": rule.id if rule else None})
        return None
    existing = db.scalar(select(ClaimDecision).where(ClaimDecision.claim_intake_id == intake.id,
                                                   ClaimDecision.decision_type == "provisional"))
    if existing:
        return existing
    ledger = db.scalar(select(LedgerProjection).where(LedgerProjection.policy_id == policy.id))
    remaining = max(0, int(plan["annual_limit"] * 100) - (ledger.ledger.get("annual_paid_fils", 0) if ledger else 0))
    amount = min(rule.max_amount_fils, remaining)
    if amount <= 0:
        log(db, intake.id, "system", "provisional_engine", "provisional_not_issued",
            {"category": category, "reason": "annual_limit_exhausted"})
        return None
    decision = ClaimDecision(claim_intake_id=intake.id, decision_type="provisional", amount_fils=amount,
                             decided_by="provisional_engine", rationale=f"Rule {rule.id}; pending final broker review",
                             net_due_fils=None)
    db.add(decision)
    db.flush()
    log(db, intake.id, "system", "provisional_engine", "provisional_issued",
        {"rule_id": rule.id, "amount_fils": amount, "category": category, "checks": checks})
    return decision


def final_amount(db, intake_id: str, amount_fils: int | None) -> tuple[int, int]:
    prior = db.scalar(select(ClaimDecision).where(ClaimDecision.claim_intake_id == intake_id,
                                                  ClaimDecision.decision_type == "provisional"))
    applied = min(prior.amount_fils or 0, amount_fils or 0) if prior else 0
    log(db, intake_id, "system", "servicing_engine", "provisional_reconciled",
        {"provisional_fils": prior.amount_fils if prior else 0, "final_fils": amount_fils or 0,
         "applied_fils": applied, "net_due_fils": max(0, (amount_fils or 0) - applied),
         "excess_for_manual_recovery_fils": max(0, (prior.amount_fils or 0) - (amount_fils or 0)) if prior else 0})
    return applied, max(0, (amount_fils or 0) - applied)


def auto_cap(db, policy, category: str, default_aed: int, confidence: float) -> int:
    rule = db.scalar(select(ClaimAutoRule).where(ClaimAutoRule.policy_type == policy.snapshot.get("plan", {}).get("id"),
                                                 ClaimAutoRule.claim_category == category,
                                                 ClaimAutoRule.active.is_(True)))
    if not rule:
        return default_aed
    return rule.max_amount_fils // 100 if confidence >= rule.min_confidence else 0


def sample_auto_decision(db, intake_id: str) -> None:
    if int(sha256(intake_id.encode()).hexdigest()[:8], 16) % 10 == 0:
        db.add(ClaimQualityAudit(claim_intake_id=intake_id))
        log(db, intake_id, "system", "quality_sampler", "audit_sampled", {"sample_rate_pct": 10})


def validate_cap_raise(db, old_fils: int, new_fils: int, policy_type: str, category: str) -> None:
    if new_fils <= old_fils:
        return
    reviewed = [(audit, intake, policy) for audit, intake, policy in db.execute(
        select(ClaimQualityAudit, ClaimIntake, Policy)
        .join(ClaimIntake, ClaimIntake.id == ClaimQualityAudit.claim_intake_id)
        .join(Policy, Policy.id == ClaimIntake.policy_id)
        .where(ClaimQualityAudit.status.in_(["correct", "incorrect"]))).all()
        if intake.structured_fields.get("benefit_class") == category
        and policy.snapshot.get("plan", {}).get("id") == policy_type]
    if len(reviewed) < 10 or sum(audit.status == "incorrect" for audit, _, _ in reviewed) / len(reviewed) > 0.02:
        raise HTTPException(409, "Higher auto caps require 10 reviewed samples and a false-auto rate no greater than 2%.")


def review_sample(db, audit: ClaimQualityAudit, reviewer_id: str, status: str, note: str) -> None:
    if audit.status != "pending":
        raise HTTPException(409, "This sample was already reviewed.")
    audit.status, audit.reviewer_id, audit.note = status, reviewer_id, note
    audit.reviewed_at = datetime.now(timezone.utc)
    log(db, audit.claim_intake_id, "broker", reviewer_id, "auto_audit_reviewed", {"status": status, "note": note})
