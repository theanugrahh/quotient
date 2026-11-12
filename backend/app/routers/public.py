from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, rate_limited
from app.errors import NotFoundError
from app.models import Invoice, InvoiceStatus
from app.payments import get_provider
from app.schemas import CheckoutOut, PublicInvoiceOut
from app.services.serializers import line_item_out

router = APIRouter(prefix="/public", tags=["public"])

public_rate_limit = rate_limited("public")


def _shared_invoice(token: str, db) -> Invoice:
    invoice = db.execute(select(Invoice).where(Invoice.share_token == token)).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("This invoice link is not valid.", code="share_not_found")
    if invoice.share_expires_at and invoice.share_expires_at < datetime.now(UTC):
        raise NotFoundError("This invoice link has expired.", code="share_expired")
    if invoice.status == InvoiceStatus.VOID:
        raise NotFoundError("This invoice is no longer available.", code="share_voided")
    return invoice


@router.get("/invoices/{token}", response_model=PublicInvoiceOut, dependencies=[Depends(public_rate_limit)])
def view_invoice(token: str, db: DbSession) -> PublicInvoiceOut:
    invoice = _shared_invoice(token, db)
    return PublicInvoiceOut(
        number=invoice.number,
        status=invoice.status,
        currency=invoice.currency,
        studio_name=invoice.owner.name,
        client_name=invoice.client.name,
        client_company=invoice.client.company,
        items=[line_item_out(item) for item in invoice.items],
        subtotal_cents=invoice.subtotal_cents,
        discount_cents=invoice.discount_cents,
        tax_cents=invoice.tax_cents,
        total_cents=invoice.total_cents,
        notes=invoice.notes,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
    )


@router.post("/invoices/{token}/checkout", response_model=CheckoutOut, dependencies=[Depends(public_rate_limit)])
def start_checkout(token: str, db: DbSession) -> CheckoutOut:
    from app.models import Payment

    invoice = _shared_invoice(token, db)
    if invoice.status == InvoiceStatus.PAID:
        raise NotFoundError("This invoice has already been paid.", code="invoice_paid")

    provider = get_provider()
    session = provider.create_checkout(
        user_id=invoice.owner_id,
        user_email=invoice.owner.email,
        plan="invoice",
        amount_cents=invoice.total_cents,
        currency=invoice.currency,
    )

    payment = Payment(
        user_id=invoice.owner_id,
        invoice_id=invoice.id,
        provider=provider.name,
        provider_ref=session.session_id,
        amount_cents=invoice.total_cents,
        currency=invoice.currency,
        status="pending",
        plan="invoice",
    )
    db.add(payment)
    db.commit()

    return CheckoutOut(session_id=session.session_id, url=session.path)
