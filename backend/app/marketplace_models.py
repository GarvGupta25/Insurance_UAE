"""Relational marketplace models introduced by Pivot v2 Phase 2.

They intentionally live apart from the established JSON-backed Helm Direct domain
models. Later marketplace phases can use provider-owned records without changing
the deterministic comparison catalogue.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, now, uid


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    is_seed_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProviderUser(Base):
    __tablename__ = "provider_users"

    # The SQL migration references auth.users. Avoiding an ORM FK keeps SQLite metadata tests portable.
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(160))


class MarketplacePlan(Base):
    __tablename__ = "marketplace_plans"
    __table_args__ = (UniqueConstraint("provider_id", "plan_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    plan_code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    terms: Mapped[dict] = mapped_column(JSON)
    is_helm_direct_reference: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MarketplaceApplication(Base):
    __tablename__ = "marketplace_applications"
    __table_args__ = (
        UniqueConstraint("case_id", "provider_id"),
        CheckConstraint(
            "status IN ('awaiting_broker_review', 'broker_approved', 'sent_to_providers', "
            "'quotes_collected', 'customer_selected', 'provider_accepted', "
            "'broker_final_review', 'bound', 'declined')"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("shopping_cases.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="awaiting_broker_review", index=True)
    consent_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProviderQuotation(Base):
    __tablename__ = "provider_quotations"
    __table_args__ = (
        UniqueConstraint("application_id", "provider_id"),
        CheckConstraint(
            "status IN ('submitted', 'shortlisted', 'selected', 'accepted', 'declined', 'withdrawn')"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(ForeignKey("marketplace_applications.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    marketplace_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("marketplace_plans.id"), nullable=True
    )
    plan_terms: Mapped[dict] = mapped_column(JSON)
    premium: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(24), default="submitted", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MarketplacePolicy(Base):
    __tablename__ = "policies_marketplace"
    __table_args__ = (
        UniqueConstraint("application_id"),
        UniqueConstraint("quotation_id"),
        CheckConstraint("status IN ('active', 'discontinued')"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("marketplace_applications.id"))
    quotation_id: Mapped[str] = mapped_column(ForeignKey("provider_quotations.id"))
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    discontinued_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class ProviderPayment(Base):
    __tablename__ = "provider_payments"
    __table_args__ = (CheckConstraint("status IN ('paid', 'due', 'overdue')"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies_marketplace.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String(24), default="paid")


class ProviderFlag(Base):
    __tablename__ = "provider_flags"
    __table_args__ = (CheckConstraint("status IN ('open', 'reviewed', 'closed')"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies_marketplace.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("providers.id"), index=True)
    reason: Mapped[str] = mapped_column(String(1000))
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
