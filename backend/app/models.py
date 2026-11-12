from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UTCDateTime(TypeDecorator):
    """Stores datetimes in UTC and always reads them back as timezone aware values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserRole:
    USER = "user"
    ADMIN = "admin"

    ALL = (USER, ADMIN)


class UserPlan:
    FREE = "free"
    PRO = "pro"

    ALL = (FREE, PRO)


class InvoiceStatus:
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    VOID = "void"

    ALL = (DRAFT, SENT, PAID, VOID)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.USER, nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default=UserPlan.FREE, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    clients: Mapped[list[Client]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Client(TimestampMixin, Base):
    __tablename__ = "clients"
    __table_args__ = (Index("ix_clients_owner_id", "owner_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), default=None, nullable=True)
    company: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    owner: Mapped[User] = relationship(back_populates="clients")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="client")


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("owner_id", "number", name="uq_invoices_owner_number"),
        Index("ix_invoices_owner_status", "owner_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=InvoiceStatus.DRAFT, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)
    issue_date: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tax_rate_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_bp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    owner: Mapped[User] = relationship(back_populates="invoices")
    client: Mapped[Client] = relationship(back_populates="invoices")
    items: Mapped[list[InvoiceItem]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.position"
    )
    attachments: Mapped[list[Attachment]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    quantity_milli: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True)
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    owner: Mapped[User] = relationship()
    invoice: Mapped[Invoice | None] = relationship(back_populates="attachments")


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_provider_ref", "provider", "provider_ref"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default=UserPlan.PRO, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)

    user: Mapped[User] = relationship()


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="processed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
