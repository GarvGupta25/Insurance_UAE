"""Member-facing catalogue matching and explicit provider consent."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .agents import explain_catalogue_ranking, rank_catalogue_plans
from .auth import User, current_user
from .contracts import readiness
from .db import session
from .marketplace_models import MarketplaceApplication, MarketplacePlan, Provider
from .models import Audit, Case, Profile, now
from .services import own

router = APIRouter(prefix="/api/marketplace", tags=["marketplace-matching"])
CONSENT_QUESTION = "Would you like me to send your details to these providers for a real quote?"
SENSITIVE_FIELDS = {"emirates_id", "passport_number"}


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent: Literal["yes", "no"]
    plan_ids: list[str] = Field(default_factory=list, max_length=3)


def catalogue(db: Session) -> list[dict]:
    rows = db.execute(
        select(MarketplacePlan, Provider)
        .join(Provider, Provider.id == MarketplacePlan.provider_id)
        .order_by(Provider.name, MarketplacePlan.plan_code)
    ).all()
    return [
        {
            "id": plan.id,
            "plan_code": plan.plan_code,
            "name": plan.name,
            "provider_id": provider.id,
            "provider_name": provider.name,
            "terms": plan.terms,
        }
        for plan, provider in rows
    ]


def create_consented_applications(
    db: Session,
    *,
    owner_id: str,
    case_id: str,
    profile: dict,
    ranked: list[dict],
    consent: str,
) -> list[MarketplaceApplication]:
    """Create and send member-selected provider requests after explicit consent."""
    if consent != "yes":
        return []

    by_provider: dict[str, list[str]] = {}
    for row in ranked:
        by_provider.setdefault(row["provider_id"], []).append(row["plan_id"])
    shared_profile = {key: value for key, value in profile.items() if key not in SENSITIVE_FIELDS}
    applications = []
    for provider_id, plan_ids in by_provider.items():
        application = db.scalar(
            select(MarketplaceApplication).where(
                MarketplaceApplication.case_id == case_id,
                MarketplaceApplication.provider_id == provider_id,
            )
        )
        if application is None:
            application = MarketplaceApplication(
                owner_id=owner_id,
                case_id=case_id,
                provider_id=provider_id,
                status="sent_to_providers",
                consent_snapshot={
                    "explicit_consent": "yes",
                    "question": CONSENT_QUESTION,
                    "ranked_plan_ids": plan_ids,
                    "shared_profile": shared_profile,
                },
            )
            db.add(application)
            db.flush()
            recent = db.scalars(
                select(MarketplaceApplication).where(
                    MarketplaceApplication.owner_id == owner_id,
                    MarketplaceApplication.provider_id == provider_id,
                    MarketplaceApplication.case_id != case_id,
                    MarketplaceApplication.created_at >= now() - timedelta(minutes=10),
                )
            ).all()
            if any(
                row.consent_snapshot.get("shared_profile") == shared_profile for row in recent
            ):
                db.add(
                    Audit(
                        owner_id=owner_id,
                        action="marketplace_anomaly_flagged",
                        subject_id=application.id,
                        details={
                            "reason": "Near-duplicate consented application",
                            "rule": "same member, provider and profile within 10 minutes",
                        },
                    )
                )
        applications.append(application)
    return applications


def _matching_context(db: Session, case_id: str, user: User) -> tuple[Profile, list[dict]]:
    own(db, Case, case_id, user)
    profile = db.scalar(select(Profile).where(Profile.owner_id == user.id))
    if profile is None or not readiness(profile.facts)["ready"]:
        raise HTTPException(409, "Complete the insurance profile before catalogue matching.")
    return profile, rank_catalogue_plans(profile.facts, catalogue(db))


@router.get("/cases/{case_id}/recommendations")
def catalogue_recommendations(
    case_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(session),
):
    _, ranked = _matching_context(db, case_id, user)
    return {
        "recommendations": ranked,
        "explanations": explain_catalogue_ranking(ranked),
        "consent_question": CONSENT_QUESTION,
    }


@router.post("/cases/{case_id}/consent")
def consent_to_providers(
    case_id: str,
    body: ConsentRequest,
    user: User = Depends(current_user),
    db: Session = Depends(session),
):
    if body.consent == "no":
        own(db, Case, case_id, user)
        return {"consent": "no", "applications": []}
    profile, ranked = _matching_context(db, case_id, user)
    if not body.plan_ids:
        raise HTTPException(422, "Choose one to three recommended plans before requesting quotations.")
    requested = set(body.plan_ids)
    ranked = [item for item in ranked if item["plan_id"] in requested]
    if len(ranked) != len(requested):
        raise HTTPException(422, "Choose plans from the five recommendations shown for this profile.")
    applications = create_consented_applications(
        db,
        owner_id=user.id,
        case_id=case_id,
        profile=profile.facts,
        ranked=ranked,
        consent=body.consent,
    )
    db.commit()
    return {
        "consent": "yes",
        "applications": [
            {"id": row.id, "provider_id": row.provider_id, "status": row.status}
            for row in applications
        ],
    }
