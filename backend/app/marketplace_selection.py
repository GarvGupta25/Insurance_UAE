"""Member quotation collection, ranking and selection for the provider marketplace."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .agents import explain_catalogue_ranking, rank_catalogue_plans
from .auth import User, current_user
from .db import session
from .marketplace_models import (
    MarketplaceApplication,
    MarketplacePolicy,
    Provider,
    ProviderQuotation,
)
from .models import Case, Profile, now
from .services import own

router = APIRouter(prefix="/api/marketplace", tags=["marketplace-selection"])
COLLECTION_WINDOW = timedelta(hours=72)


def _case_applications(db: Session, case_id: str, user: User) -> list[MarketplaceApplication]:
    own(db, Case, case_id, user)
    return list(
        db.scalars(
            select(MarketplaceApplication)
            .where(
                MarketplaceApplication.case_id == case_id,
                MarketplaceApplication.owner_id == user.id,
            )
            .order_by(MarketplaceApplication.created_at)
        ).all()
    )


def _quotation_rows(db: Session, applications: list[MarketplaceApplication]):
    application_ids = [row.id for row in applications]
    if not application_ids:
        return []
    return db.execute(
        select(ProviderQuotation, MarketplaceApplication, Provider)
        .join(MarketplaceApplication, MarketplaceApplication.id == ProviderQuotation.application_id)
        .join(Provider, Provider.id == ProviderQuotation.provider_id)
        .where(ProviderQuotation.application_id.in_(application_ids))
        .order_by(ProviderQuotation.submitted_at)
    ).all()


def _collection_ready(applications: list[MarketplaceApplication], quotation_count: int) -> bool:
    if not applications or quotation_count == 0:
        return False
    # A member may accept a provider's submitted quotation immediately rather
    # than waiting for every selected provider to reply.
    if quotation_count > 0:
        return True
    current = now()
    created_at = applications[0].created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=current.tzinfo)
    return quotation_count == len(applications) or current - created_at >= COLLECTION_WINDOW


def rank_real_quotations(profile: dict, rows: list[tuple]) -> list[dict]:
    """Reuse Phase 4 scoring with provider-submitted premiums and terms as the only plan inputs."""
    source = {}
    catalogue = []
    for quotation, application, provider in rows:
        if quotation.status in {"declined", "withdrawn"}:
            continue
        terms = {**quotation.plan_terms, "annual_premium": float(quotation.premium)}
        terms.setdefault("id", quotation.id)
        terms.setdefault("name", f"{provider.name} quotation")
        item = {
            "id": quotation.id,
            "plan_code": quotation.id,
            "provider_id": provider.id,
            "provider_name": provider.name,
            "name": terms["name"],
            "terms": terms,
        }
        source[quotation.id] = (quotation, application, provider, terms)
        catalogue.append(item)
    ranked = rank_catalogue_plans(profile, catalogue)[:3]
    if not ranked:
        return []
    explanations = {
        row["plan_id"]: row["explanation"] for row in explain_catalogue_ranking(ranked)
    }
    result = []
    for row in ranked:
        quotation, application, provider, terms = source[row["plan_id"]]
        result.append(
            {
                **row,
                "quotation_id": quotation.id,
                "application_id": application.id,
                "provider_name": provider.name,
                "premium_aed": float(quotation.premium),
                "terms": terms,
                "status": quotation.status,
                "explanation": explanations[row["plan_id"]],
            }
        )
    return result


def _status_payload(db: Session, case_id: str, user: User, *, persist: bool = True) -> dict:
    applications = _case_applications(db, case_id, user)
    rows = _quotation_rows(db, applications)
    ready = _collection_ready(applications, len(rows))
    if ready:
        quoted_application_ids = {quotation.application_id for quotation, _, _ in rows}
        for application in applications:
            if application.status == "sent_to_providers":
                application.status = (
                    "quotes_collected" if application.id in quoted_application_ids else "declined"
                )
    profile = db.scalar(select(Profile).where(Profile.owner_id == user.id))
    ranked = rank_real_quotations(profile.facts, rows) if ready and profile else []
    updates = [
        {
            "quotation_id": quotation.id,
            "provider_name": provider.name,
            "premium_aed": float(quotation.premium),
            "terms": quotation.plan_terms,
            "status": quotation.status,
        }
        for quotation, _, provider in rows
        if quotation.status not in {"declined", "withdrawn"}
    ]
    if persist:
        db.commit()
    active = next(
        (
            row
            for row in applications
            if row.status in {"bound", "broker_final_review", "provider_accepted", "customer_selected"}
        ),
        None,
    )
    return {
        "case_id": case_id,
        "status": (
            active.status
            if active
            else "quotes_collected"
            if ready
            else "quotation_received"
            if rows
            else "sent_to_providers"
        ),
        "collection_ready": ready,
        "responded": len(rows),
        "invited": len(applications),
        "collection_window_hours": int(COLLECTION_WINDOW.total_seconds() / 3600),
        "quotations": ranked,
        "updates": updates,
    }


@router.get("/applications")
def member_marketplace_applications(
    user: User = Depends(current_user), db: Session = Depends(session)
):
    rows = db.execute(
        select(MarketplaceApplication.case_id, MarketplaceApplication.status)
        .where(MarketplaceApplication.owner_id == user.id)
        .order_by(MarketplaceApplication.created_at.desc())
    ).all()
    grouped = {}
    for case_id, status in rows:
        grouped.setdefault(case_id, status)
    return [{"case_id": case_id, "status": status} for case_id, status in grouped.items()]


@router.get("/notifications")
def member_marketplace_notifications(
    user: User = Depends(current_user), db: Session = Depends(session)
):
    rows = db.execute(
        select(MarketplaceApplication, Provider)
        .join(Provider, Provider.id == MarketplaceApplication.provider_id)
        .where(MarketplaceApplication.owner_id == user.id)
        .order_by(MarketplaceApplication.created_at.desc())
    ).all()
    messages = {
        "sent_to_providers": "Your selected provider has received your quotation request.",
        "quotes_collected": "A provider quotation is ready to compare.",
        "customer_selected": "Your selected quotation is waiting for provider acceptance.",
        "bound": "Your provider has started your demonstration policy.",
    }
    result = []
    for application, provider in rows:
        quotation = db.scalar(
            select(ProviderQuotation).where(ProviderQuotation.application_id == application.id)
        )
        quote_ready = quotation is not None and quotation.status not in {"declined", "withdrawn"}
        result.append(
            {
                "case_id": application.case_id,
                "provider": provider.name,
                "status": application.status,
                "message": (
                    f"{provider.name} submitted a quotation. Open it to review the terms."
                    if quote_ready and application.status == "sent_to_providers"
                    else messages.get(application.status, "Your marketplace request has an update.")
                ),
                "new_quotation": quote_ready,
            }
        )
    return result


@router.get("/cases/{case_id}/quotations")
def marketplace_quotations(
    case_id: str, user: User = Depends(current_user), db: Session = Depends(session)
):
    return _status_payload(db, case_id, user)


@router.post("/quotations/{quotation_id}/select")
def select_quotation(
    quotation_id: str, user: User = Depends(current_user), db: Session = Depends(session)
):
    selected = db.scalar(
        select(ProviderQuotation)
        .join(MarketplaceApplication)
        .where(
            ProviderQuotation.id == quotation_id,
            MarketplaceApplication.owner_id == user.id,
        )
        .with_for_update()
    )
    if selected is None:
        raise HTTPException(404, "Quotation not found.")
    selected_application = db.get(MarketplaceApplication, selected.application_id)
    applications = _case_applications(db, selected_application.case_id, user)
    rows = _quotation_rows(db, applications)
    for quotation, application, _ in rows:
        chosen = quotation.id == quotation_id
        quotation.status = "selected" if chosen else "declined"
        application.status = "customer_selected" if chosen else "declined"
    for application in applications:
        if application.id != selected_application.id and not any(row[1].id == application.id for row in rows):
            application.status = "declined"
    db.commit()
    return {
        "quotation_id": selected.id,
        "application_id": selected.application_id,
        "status": selected.status,
        "notification": "The selected provider can now accept this quotation.",
    }


@router.get("/policies")
def member_marketplace_policies(
    user: User = Depends(current_user), db: Session = Depends(session)
):
    rows = db.execute(
        select(MarketplacePolicy, ProviderQuotation, Provider)
        .join(ProviderQuotation, ProviderQuotation.id == MarketplacePolicy.quotation_id)
        .join(Provider, Provider.id == MarketplacePolicy.provider_id)
        .where(MarketplacePolicy.owner_id == user.id)
        .order_by(MarketplacePolicy.started_at.desc())
    ).all()
    return [
        {
            "id": policy.id,
            "status": policy.status,
            "provider": provider.name,
            "premium": float(quotation.premium),
            "terms": quotation.plan_terms,
            "started_at": policy.started_at.isoformat(),
        }
        for policy, quotation, provider in rows
    ]
