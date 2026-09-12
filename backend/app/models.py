from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Owned:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Profile(Owned, Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("owner_id"),)
    version: Mapped[int] = mapped_column(Integer, default=1)
    facts: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class ProfileVersion(Owned, Base):
    __tablename__ = "profile_versions"
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"))
    version: Mapped[int]
    facts: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("profile_id", "version"),)


class Case(Owned, Base):
    __tablename__ = "shopping_cases"
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(40), default="intake")


class Message(Owned, Base):
    __tablename__ = "messages"
    case_id: Mapped[str] = mapped_column(ForeignKey("shopping_cases.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(String(12000))
    modality: Mapped[str] = mapped_column(String(16), default="text")
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Run(Owned, Base):
    __tablename__ = "agent_runs"
    case_id: Mapped[str] = mapped_column(ForeignKey("shopping_cases.id"))
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)


class Quote(Owned, Base):
    __tablename__ = "quotes"
    case_id: Mapped[str] = mapped_column(ForeignKey("shopping_cases.id"))
    profile_version: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)


class Application(Owned, Base):
    __tablename__ = "applications"
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"))
    status: Mapped[str] = mapped_column(String(40), default="ready_for_confirmation")
    snapshot: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))


class Policy(Owned, Base):
    __tablename__ = "policies"
    application_id: Mapped[str | None] = mapped_column(
        ForeignKey("applications.id"), unique=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="demo_active")
    snapshot: Mapped[dict] = mapped_column(JSON)


class Installment(Owned, Base):
    __tablename__ = "instalments"
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"))
    position: Mapped[int]
    due_date: Mapped[str] = mapped_column(String(10))
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3), default="AED")
    status: Mapped[str] = mapped_column(String(24), default="due")
    __table_args__ = (UniqueConstraint("policy_id", "position"),)


class PaymentOrder(Owned, Base):
    __tablename__ = "payment_orders"
    installment_id: Mapped[str] = mapped_column(ForeignKey("instalments.id"))
    provider: Mapped[str] = mapped_column(String(24))
    provider_order_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="created")
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))


class Receipt(Owned, Base):
    __tablename__ = "receipts"
    order_id: Mapped[str] = mapped_column(ForeignKey("payment_orders.id"), unique=True)
    installment_id: Mapped[str] = mapped_column(ForeignKey("instalments.id"), unique=True)
    provider_payment_id: Mapped[str] = mapped_column(String(100), unique=True)
    amount: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    provider: Mapped[str] = mapped_column(String(24))


class Document(Owned, Base):
    __tablename__ = "documents"
    kind: Mapped[str] = mapped_column(String(24), default="identity")
    sha256: Mapped[str] = mapped_column(String(64))
    extraction: Mapped[dict] = mapped_column(JSON)
    accepted: Mapped[bool] = mapped_column(default=False)


class Command(Owned, Base):
    __tablename__ = "command_receipts"
    key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("owner_id", "key"),)


class Audit(Owned, Base):
    __tablename__ = "audit_events"
    action: Mapped[str] = mapped_column(String(60))
    subject_id: Mapped[str] = mapped_column(String(36))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
