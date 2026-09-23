"""Scoped, read-only claim analysis. Only servicing.py can record money decisions."""

from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import ClaimAuditLog, ClaimDocument, ClaimFinding, ClaimFlag, ClaimIntake, OnCallRoster, Policy


def log(db: Session, claim_id: str, actor_type: str, actor_id: str, action: str, payload: dict) -> None:
    db.add(ClaimAuditLog(claim_intake_id=claim_id, actor_type=actor_type, actor_id=actor_id,
                         action=action, payload=payload))


def finding(db: Session, claim_id: str, agent: str, kind: str, payload: dict, confidence: float) -> None:
    db.add(ClaimFinding(claim_intake_id=claim_id, agent_name=agent, finding_type=kind,
                        payload=payload, confidence=confidence))
    log(db, claim_id, "agent", agent, "finding_recorded", {"type": kind, "confidence": confidence, "output": payload})


def analyze(db: Session, intake: ClaimIntake, policy: Policy, required_documents: dict[str, tuple[str, ...]]) -> dict:
    """All inputs are already validated fields or document metadata; no document text enters a tool prompt."""
    fields = intake.structured_fields
    expected = ("event_id", "policy_month", "provider_tier", "benefit_class")
    if intake.raw_message:
        expected = (*expected, "provider_name")
    amount_name = {"claim": "billed_amount", "pre_auth": "estimated_amount",
                   "reimbursement": "amount_paid_by_member"}.get(intake.kind)
    observed = [*expected, *([amount_name] if amount_name else [])]
    missing = [name for name in observed if fields.get(name) is None or fields.get(name) == ""]
    confidence = mean(1.0 if name not in missing else 0.0 for name in observed)
    finding(db, intake.id, "intake_extraction", "extracted_fields",
            {"fields": {name: fields.get(name) for name in observed}, "missing_required": missing,
             "field_confidence": {name: 1.0 if name not in missing else 0.0 for name in observed}}, confidence)

    documents = db.scalars(select(ClaimDocument).where(ClaimDocument.claim_intake_id == intake.id)).all()
    present = sorted({doc.doc_type for doc in documents if doc.completeness_ok})
    required = list(required_documents.get(intake.kind, ()))
    absent = [doc for doc in required if doc not in present]
    docs_complete = not absent and {doc.doc_type for doc in documents}.issubset(present)
    finding(db, intake.id, "document_verification", "document_check",
            {"required_docs": required, "present_docs": present, "missing_docs": absent,
             "issues": [doc.doc_type for doc in documents if not doc.completeness_ok]},
            1.0 if docs_complete else 0.0)

    plan = policy.snapshot.get("plan", {})
    benefit = fields.get("benefit_class")
    clauses = []
    assessment = "unclear"
    if policy.status == "demo_active" and plan:
        if benefit in {"maternity", "chronic_preexisting"}:
            term = plan.get(benefit)
            if isinstance(term, dict) and isinstance(term.get("covered"), bool):
                clauses.append({"clause_id": f"plan.{benefit}.covered", "text_snippet": str(term)[:300]})
                assessment = "covered" if term["covered"] else "excluded"
        elif benefit in {"general", "dental_optical"} and isinstance(plan.get("annual_limit"), (int, float)):
            clause = "annual_limit" if benefit == "general" else "dental_optical"
            if clause in plan:
                clauses.append({"clause_id": f"plan.{clause}", "text_snippet": str(plan[clause])[:300]})
                assessment = "excluded" if plan[clause] == "none" else "covered"
    finding(db, intake.id, "eligibility_policy_match", "coverage_assessment",
            {"assessment": assessment, "cited_clauses": clauses,
             "note": "Indicative policy match only; deterministic servicing decides."},
            1.0 if clauses else 0.0)

    flags = db.scalars(select(ClaimFlag).where(ClaimFlag.claim_intake_id == intake.id,
                                               ClaimFlag.status == "open")).all()
    duplicate = any(flag.flag_type == "anomaly" and "same provider" in flag.reason for flag in flags)
    risk = {"duplicate_score": 1.0 if duplicate else 0.0,
            "anomaly_flags": [flag.reason for flag in flags if flag.flag_type == "anomaly"]}
    finding(db, intake.id, "risk_signal", "risk_assessment", risk, 1.0)
    return {"confidence": confidence, "docs_complete": docs_complete, "eligibility": assessment,
            "duplicate_score": risk["duplicate_score"], "missing_docs": absent, "missing_fields": missing,
            "cited_clauses": clauses, "anomaly_flags": risk["anomaly_flags"]}


def brief(db: Session, intake: ClaimIntake, analysis: dict, route: str) -> None:
    if route == "auto_decision":
        return
    action = "request_more_information" if analysis["missing_docs"] or analysis["missing_fields"] else "escalate_to_senior_broker"
    payload = {"summary": (intake.raw_message or intake.structured_fields.get("description") or intake.kind)[:300],
               "key_facts": intake.structured_fields, "document_status": analysis["missing_docs"],
               "eligibility": analysis["eligibility"], "cited_clauses": analysis["cited_clauses"],
               "risk_flags": analysis["anomaly_flags"], "suggested_action": action,
               "rationale": "A broker must review the recorded findings.", "advisory_only": True}
    finding(db, intake.id, "broker_brief", "case_brief", payload, analysis["confidence"])


def page_oncall(db: Session, intake: ClaimIntake) -> dict:
    now = datetime.now(timezone.utc)
    roster = db.scalar(select(OnCallRoster).where(OnCallRoster.is_active.is_(True),
                                                  OnCallRoster.shift_start <= now,
                                                  OnCallRoster.shift_end > now)
                       .order_by(OnCallRoster.shift_start.desc()))
    url = settings().oncall_webhook_url
    if not roster or not url:
        result = {"sent": False, "reason": "No staffed on-call shift or paging connection is configured."}
    else:
        try:
            token = getattr(settings(), "oncall_webhook_token", "")
            response = httpx.post(url, json={"claim_id": intake.id, "broker_id": roster.broker_id,
                                             "priority": "emergency", "created_at": intake.created_at.isoformat()},
                                  headers={"Authorization": f"Bearer {token}"} if token else {}, timeout=5)
            response.raise_for_status()
            result = {"sent": True, "broker_id": roster.broker_id}
        except httpx.HTTPError:
            result = {"sent": False, "reason": "The on-call page could not be delivered."}
    log(db, intake.id, "system", "oncall_pager", "page_attempted", result)
    return result
