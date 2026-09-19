"""Broker-facing marketplace checkpoints and case comparison."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import User, require_broker
from .db import session
from .marketplace_models import (
    MarketplaceApplication,
    Provider,
    ProviderFlag,
    ProviderQuotation,
)
from .models import BrokerAssignment, Recommendation, ReviewDecision
from .services import assigned

router = APIRouter(prefix="/api/broker/marketplace", tags=["broker-marketplace"])


class CheckpointReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve"] = "approve"
    note: Annotated[str, Field(max_length=2000)] = ""
    edits: dict = Field(default_factory=dict)


def checkpoint_one_approved_for_case(db: Session, case_id: str) -> bool:
    return (
        db.scalar(
            select(ReviewDecision.id)
            .join(Recommendation, ReviewDecision.recommendation_id == Recommendation.id)
            .where(
                Recommendation.case_id == case_id,
                Recommendation.status == "approved",
                ReviewDecision.action.in_(("approve", "edit")),
            )
        )
        is not None
    )


def checkpoint_one_approved(db: Session, application: MarketplaceApplication) -> bool:
    return checkpoint_one_approved_for_case(db, application.case_id)


def advance_to_providers(db: Session, application: MarketplaceApplication) -> None:
    """Apply the Phase 3 API guard from every provider-send path."""
    if application.status != "broker_approved":
        raise HTTPException(409, "Only a broker-approved application can be sent to a provider.")
    if not checkpoint_one_approved(db, application):
        raise HTTPException(403, "Checkpoint 1 approval is required before provider submission.")
    application.status = "sent_to_providers"


def checkpoint_two_approved(db: Session, application: MarketplaceApplication) -> bool:
    return (
        db.scalar(
            select(ReviewDecision.id).where(
                ReviewDecision.marketplace_application_id == application.id,
                ReviewDecision.checkpoint == "checkpoint_2",
                ReviewDecision.action == "approve",
            )
        )
        is not None
    )


def accepted_quotation(db: Session, application: MarketplaceApplication) -> ProviderQuotation | None:
    return db.scalar(
        select(ProviderQuotation).where(
            ProviderQuotation.application_id == application.id,
            ProviderQuotation.status == "accepted",
        )
    )


def require_binding_approval(db: Session, application: MarketplaceApplication) -> ProviderQuotation:
    quotation = accepted_quotation(db, application)
    if quotation is None:
        raise HTTPException(409, "The provider quotation must be accepted before policy binding.")
    if not checkpoint_two_approved(db, application):
        raise HTTPException(403, "Checkpoint 2 approval is required before policy binding.")
    return quotation


def _age_days(current: datetime, created_at: datetime) -> int:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=current.tzinfo)
    return max(0, (current - created_at).days)


def marketplace_worklist_items(db: Session, user: User, current: datetime) -> list[dict]:
    applications = db.scalars(
        select(MarketplaceApplication)
        .join(BrokerAssignment, BrokerAssignment.member_id == MarketplaceApplication.owner_id)
        .where(
            BrokerAssignment.broker_id == user.id,
            MarketplaceApplication.status.in_(("awaiting_broker_review", "provider_accepted")),
        )
    ).all()
    items = []
    for application in applications:
        checkpoint = 1 if application.status == "awaiting_broker_review" else 2
        age_days = _age_days(current, application.created_at)
        items.append(
            {
                "id": application.id,
                "item_type": f"marketplace_checkpoint_{checkpoint}",
                "applicant_id": application.owner_id,
                "case_id": application.case_id,
                "age_days": age_days,
                "amount_aed": 0,
                "priority_reason": (
                    f"{age_days} day(s) unresolved; Checkpoint {checkpoint} blocks "
                    f"{'provider submission' if checkpoint == 1 else 'policy binding'}."
                ),
            }
        )
    flags = db.scalars(
        select(ProviderFlag)
        .join(BrokerAssignment, BrokerAssignment.member_id == ProviderFlag.owner_id)
        .where(BrokerAssignment.broker_id == user.id, ProviderFlag.status == "open")
    ).all()
    for flag in flags:
        age_days = _age_days(current, flag.created_at)
        items.append(
            {
                "id": flag.id,
                "item_type": "provider_flag",
                "applicant_id": flag.owner_id,
                "case_id": None,
                "age_days": age_days,
                "amount_aed": 0,
                "priority_reason": f"{age_days} day(s) unresolved; provider flag requires review.",
            }
        )
    return items


@router.get("/applications")
def applications(user: User = Depends(require_broker), db: Session = Depends(session)):
    rows = db.scalars(
        select(MarketplaceApplication)
        .join(BrokerAssignment, BrokerAssignment.member_id == MarketplaceApplication.owner_id)
        .where(BrokerAssignment.broker_id == user.id)
        .order_by(MarketplaceApplication.created_at)
    ).all()
    return [
        {
            "id": row.id,
            "case_id": row.case_id,
            "applicant_id": row.owner_id,
            "provider_id": row.provider_id,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/applications/{application_id}")
def application_detail(
    application_id: str,
    user: User = Depends(require_broker),
    db: Session = Depends(session),
):
    application = assigned(db, MarketplaceApplication, application_id, user)
    sibling_ids = select(MarketplaceApplication.id).where(
        MarketplaceApplication.case_id == application.case_id
    )
    quotations = db.execute(
        select(ProviderQuotation, Provider)
        .join(Provider, Provider.id == ProviderQuotation.provider_id)
        .where(ProviderQuotation.application_id.in_(sibling_ids))
        .order_by(ProviderQuotation.submitted_at)
    ).all()
    checkpoint_one = db.execute(
        select(ReviewDecision, Recommendation)
        .join(Recommendation, ReviewDecision.recommendation_id == Recommendation.id)
        .where(
            Recommendation.case_id == application.case_id,
            Recommendation.status == "approved",
        )
        .order_by(ReviewDecision.created_at)
    ).all()
    checkpoint_two = db.scalars(
        select(ReviewDecision)
        .where(
            ReviewDecision.marketplace_application_id.in_(sibling_ids),
            ReviewDecision.checkpoint == "checkpoint_2",
        )
        .order_by(ReviewDecision.created_at)
    ).all()
    history = [
        {
            "checkpoint": "checkpoint_1",
            "approved_by": review.owner_id,
            "approved_at": review.created_at.isoformat(),
            "action": review.action,
            "note": review.note,
            "edits": review.after,
        }
        for review, _ in checkpoint_one
    ] + [
        {
            "checkpoint": "checkpoint_2",
            "approved_by": review.owner_id,
            "approved_at": review.created_at.isoformat(),
            "action": review.action,
            "note": review.note,
            "edits": review.after,
        }
        for review in checkpoint_two
    ]
    return {
        "id": application.id,
        "case_id": application.case_id,
        "applicant_id": application.owner_id,
        "status": application.status,
        "quotations": [
            {
                "id": quotation.id,
                "provider": provider.name,
                "premium": float(quotation.premium),
                "key_terms": quotation.plan_terms,
                "status": quotation.status,
                "submitted_at": quotation.submitted_at.isoformat(),
            }
            for quotation, provider in quotations
        ],
        "checkpoint_history": sorted(history, key=lambda item: item["approved_at"]),
    }


@router.post("/applications/{application_id}/send")
def send_to_providers(
    application_id: str,
    user: User = Depends(require_broker),
    db: Session = Depends(session),
):
    application = assigned(db, MarketplaceApplication, application_id, user, lock=True)
    advance_to_providers(db, application)
    db.commit()
    return {"id": application.id, "status": application.status}


@router.post("/applications/{application_id}/checkpoint-2")
def approve_checkpoint_two(
    application_id: str,
    body: CheckpointReview,
    user: User = Depends(require_broker),
    db: Session = Depends(session),
):
    application = assigned(db, MarketplaceApplication, application_id, user, lock=True)
    if application.status != "provider_accepted":
        raise HTTPException(409, "Checkpoint 2 requires provider acceptance.")
    quotation = accepted_quotation(db, application)
    if quotation is None:
        raise HTTPException(409, "Checkpoint 2 requires an accepted provider quotation.")
    if checkpoint_two_approved(db, application):
        raise HTTPException(409, "Checkpoint 2 was already approved.")
    db.add(
        ReviewDecision(
            owner_id=user.id,
            marketplace_application_id=application.id,
            checkpoint="checkpoint_2",
            action=body.action,
            note=body.note,
            before={"status": application.status, "quotation_id": quotation.id},
            after={"status": "broker_final_review", "edits": body.edits},
        )
    )
    application.status = "broker_final_review"
    db.commit()
    return {"id": application.id, "status": application.status}


@router.post("/applications/{application_id}/binding-readiness")
def binding_readiness(
    application_id: str,
    user: User = Depends(require_broker),
    db: Session = Depends(session),
):
    application = assigned(db, MarketplaceApplication, application_id, user, lock=True)
    quotation = require_binding_approval(db, application)
    return {"ready": True, "quotation_id": quotation.id}
