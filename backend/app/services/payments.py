from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import Invoice, InvoiceStatus, Payment, User, UserPlan, WebhookEvent
from app.payments.base import PaymentEvent

logger = get_logger("app.payments")


def record_event(db: Session, provider: str, event_id: str, event_type: str) -> bool:
    """Store the event id. Returns False when the event was already handled."""
    db.add(WebhookEvent(provider=provider, event_id=event_id, event_type=event_type))
    try:
        db.flush()
    except IntegrityError as exc:
        logger.warning("duplicate_webhook_event provider=%s event_id=%s detail=%s", provider, event_id, exc.orig)
        db.rollback()
        return False
    return True


def find_payment(db: Session, provider: str, provider_ref: str) -> Payment | None:
    return db.execute(
        select(Payment).where(Payment.provider == provider, Payment.provider_ref == provider_ref)
    ).scalar_one_or_none()


def apply_payment_event(db: Session, event: PaymentEvent, provider: str) -> str:
    """Apply a verified payment event. Safe to call more than once."""
    if event.status not in {"paid", "succeeded"}:
        return "ignored"

    payment = find_payment(db, provider, event.provider_ref)
    if payment is None:
        return "no_matching_payment"
    if payment.status in {"paid", "succeeded"}:
        return "already_applied"

    payment.status = "paid"

    if payment.invoice_id:
        invoice = db.get(Invoice, payment.invoice_id)
        if invoice is not None and invoice.status != InvoiceStatus.PAID:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.now(UTC)
    else:
        user = db.get(User, payment.user_id)
        if user is not None:
            user.plan = UserPlan.PRO

    return "applied"
