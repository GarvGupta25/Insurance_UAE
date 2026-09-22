"""Provider-owned marketplace workspace with mandatory tenant isolation."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import ProviderIdentity, require_provider
from .db import session
from .marketplace_models import (
    MarketplaceApplication,
    MarketplacePolicy,
    ProviderFlag,
    ProviderPayment,
    ProviderQuotation,
)
from .models import Policy

router = APIRouter(prefix="/api/provider", tags=["provider"])


class BenefitTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")
    covered: bool
    waiting_period_months: Annotated[int, Field(ge=0, le=120)] | None = None
    limit: Annotated[Decimal, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def require_wait_when_covered(self):
        if self.covered and self.waiting_period_months is None:
            raise ValueError("A covered benefit requires a waiting period.")
        return self


class PlanTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str | None, Field(max_length=160)] = None
    network: Literal["restricted", "standard", "wide"]
    annual_limit: Annotated[Decimal, Field(gt=0)]
    deductible: Annotated[Decimal, Field(ge=0)]
    outpatient_copay_pct: Annotated[int, Field(ge=0, le=100)]
    maternity: BenefitTerms
    chronic_preexisting: BenefitTerms


class QuoteSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    premium: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    plan_terms: PlanTerms
    marketplace_plan_id: str | None = None


class DiscontinueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, Field(min_length=3, max_length=2000)]


class FlagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, Field(min_length=3, max_length=1000)]
    note: Annotated[str | None, Field(max_length=2000)] = None


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: Literal["summarize_application", "draft_quotation", "flag_anomalies"]


def _application(db: Session, application_id: str, provider: ProviderIdentity):
    row = db.scalar(
        select(MarketplaceApplication).where(
            MarketplaceApplication.id == application_id,
            MarketplaceApplication.provider_id == provider.provider_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Application not found.")
    return row


def _quotation(db: Session, quotation_id: str, provider: ProviderIdentity):
    row = db.scalar(
        select(ProviderQuotation).where(
            ProviderQuotation.id == quotation_id,
            ProviderQuotation.provider_id == provider.provider_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Quotation not found.")
    return row


def _policy(db: Session, policy_id: str, provider: ProviderIdentity):
    row = db.scalar(
        select(MarketplacePolicy).where(
            MarketplacePolicy.id == policy_id,
            MarketplacePolicy.provider_id == provider.provider_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Policy not found.")
    return row


def _application_payload(row: MarketplaceApplication) -> dict:
    return {
        "id": row.id,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "consent_snapshot": row.consent_snapshot,
    }


def _quotation_payload(row: ProviderQuotation) -> dict:
    return {
        "id": row.id,
        "application_id": row.application_id,
        "marketplace_plan_id": row.marketplace_plan_id,
        "plan_terms": row.plan_terms,
        "premium": float(row.premium),
        "status": row.status,
        "submitted_at": row.submitted_at.isoformat(),
    }


def _policy_payload(row: MarketplacePolicy) -> dict:
    return {
        "id": row.id,
        "application_id": row.application_id,
        "quotation_id": row.quotation_id,
        "status": row.status,
        "started_at": row.started_at.isoformat(),
        "discontinued_reason": row.discontinued_reason,
    }


@router.get("/applications")
def applications(
    provider: ProviderIdentity = Depends(require_provider), db: Session = Depends(session)
):
    rows = db.scalars(
        select(MarketplaceApplication)
        .where(
            MarketplaceApplication.provider_id == provider.provider_id,
            MarketplaceApplication.status == "sent_to_providers",
        )
        .order_by(MarketplaceApplication.created_at)
    ).all()
    return [_application_payload(row) for row in rows]


@router.post("/applications/{application_id}/quote", status_code=201)
def submit_quote(
    application_id: str,
    body: QuoteSubmission,
    provider: ProviderIdentity = Depends(require_provider),
    db: Session = Depends(session),
):
    application = _application(db, application_id, provider)
    if application.status != "sent_to_providers":
        raise HTTPException(409, "Only a newly received application can be quoted.")
    quotation = ProviderQuotation(
        application_id=application.id,
        provider_id=provider.provider_id,
        marketplace_plan_id=body.marketplace_plan_id,
        plan_terms=body.plan_terms.model_dump(mode="json", exclude_none=True),
        premium=body.premium,
    )
    db.add(quotation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A quotation already exists for this application.") from None
    db.refresh(quotation)
    return _quotation_payload(quotation)


@router.get("/quotations")
def quotations(
    provider: ProviderIdentity = Depends(require_provider), db: Session = Depends(session)
):
    rows = db.scalars(
        select(ProviderQuotation)
        .where(ProviderQuotation.provider_id == provider.provider_id)
        .order_by(ProviderQuotation.submitted_at.desc())
    ).all()
    return [_quotation_payload(row) for row in rows]


@router.post("/quotations/{quotation_id}/accept")
def accept_quotation(
    quotation_id: str,
    provider: ProviderIdentity = Depends(require_provider),
    db: Session = Depends(session),
):
    quotation = _quotation(db, quotation_id, provider)
    if quotation.status != "selected":
        raise HTTPException(409, "Only the customer's selected quotation can be accepted.")
    application = _application(db, quotation.application_id, provider)
    quotation.status = "accepted"
    existing = db.scalar(
        select(MarketplacePolicy).where(MarketplacePolicy.application_id == application.id)
    )
    if existing is None:
        marketplace_policy = MarketplacePolicy(
            owner_id=application.owner_id,
            application_id=application.id,
            quotation_id=quotation.id,
            provider_id=provider.provider_id,
        )
        db.add(marketplace_policy)
        terms = dict(quotation.plan_terms)
        plan = {
            **terms,
            "id": quotation.id,
            "name": terms.get("name") or "Marketplace health policy",
            "annual_premium": float(quotation.premium),
        }
        db.add(
            Policy(
                owner_id=application.owner_id,
                status="demo_active",
                snapshot={
                    "plan": plan,
                    "start_date": date.today().isoformat(),
                    "payment_frequency": "annual",
                    "marketplace_policy_id": marketplace_policy.id,
                },
            )
        )
    application.status = "bound"
    db.commit()
    return _quotation_payload(quotation)


@router.post("/policies/{quotation_id}/start", status_code=201)
def start_policy(
    quotation_id: str,
    provider: ProviderIdentity = Depends(require_provider),
    db: Session = Depends(session),
):
    quotation = _quotation(db, quotation_id, provider)
    application = _application(db, quotation.application_id, provider)
    if quotation.status != "accepted":
        raise HTTPException(409, "Only an accepted quotation can start a policy.")
    existing = db.scalar(
        select(MarketplacePolicy).where(MarketplacePolicy.application_id == application.id)
    )
    if existing is not None:
        raise HTTPException(409, "A policy already exists for this application.")
    policy = MarketplacePolicy(
        owner_id=application.owner_id,
        application_id=application.id,
        quotation_id=quotation.id,
        provider_id=provider.provider_id,
    )
    db.add(policy)
    # The database policy trigger checks the pre-bind application state before allowing the insert.
    db.flush()
    application.status = "bound"
    db.commit()
    db.refresh(policy)
    return _policy_payload(policy)


@router.get("/policies")
def policies(
    provider: ProviderIdentity = Depends(require_provider), db: Session = Depends(session)
):
    rows = db.scalars(
        select(MarketplacePolicy)
        .where(MarketplacePolicy.provider_id == provider.provider_id)
        .order_by(MarketplacePolicy.started_at.desc())
    ).all()
    return [_policy_payload(row) for row in rows]


@router.post("/policies/{policy_id}/discontinue")
def discontinue_policy(
    policy_id: str,
    body: DiscontinueRequest,
    provider: ProviderIdentity = Depends(require_provider),
    db: Session = Depends(session),
):
    policy = _policy(db, policy_id, provider)
    if policy.status != "active":
        raise HTTPException(409, "This policy is already discontinued.")
    policy.status = "discontinued"
    policy.discontinued_reason = body.reason
    db.commit()
    return _policy_payload(policy)


@router.get("/policies/{policy_id}/payments")
def policy_payments(
    policy_id: str,
    provider: ProviderIdentity = Depends(require_provider),
    db: Session = Depends(session),
):
    _policy(db, policy_id, provider)
    rows = db.scalars(
        select(ProviderPayment)
        .where(ProviderPayment.policy_id == policy_id)
        .order_by(ProviderPayment.paid_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "amount": float(row.amount),
            "status": row.status,
            "paid_at": row.paid_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/policies/{policy_id}/flags", status_code=201)
def create_flag(
    policy_id: str,
    body: FlagRequest,
    provider: ProviderIdentity = Depends(require_provider),
    db: Session = Depends(session),
):
    policy = _policy(db, policy_id, provider)
    flag = ProviderFlag(
        owner_id=policy.owner_id,
        policy_id=policy.id,
        provider_id=provider.provider_id,
        reason=body.reason,
        note=body.note,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return {"id": flag.id, "status": flag.status, "reason": flag.reason, "note": flag.note}


@router.post("/applications/{application_id}/assistant")
def provider_assistant(
    application_id: str,
    body: AssistantRequest,
    provider: ProviderIdentity = Depends(require_provider),
    db: Session = Depends(session),
):
    """A deterministic drafting aid; its only input is an already provider-scoped snapshot."""
    application = _application(db, application_id, provider)
    snapshot = application.consent_snapshot or {}
    populated = sorted(key.replace("_", " ") for key, value in snapshot.items() if value)
    missing = sorted(key.replace("_", " ") for key, value in snapshot.items() if not value)
    if body.task == "summarize_application":
        result = "Consented application includes: " + (", ".join(populated) or "no populated fields") + "."
    elif body.task == "draft_quotation":
        result = "Draft terms against the consented needs, state every limit and exclusion, and confirm the premium before submission."
    else:
        result = "Review missing or empty fields: " + (", ".join(missing) or "none detected") + "."
    return {"application_id": application.id, "task": body.task, "draft": result}
