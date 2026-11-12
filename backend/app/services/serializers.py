from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invoice, InvoiceStatus
from app.schemas import InvoiceOut, InvoiceSummary, LineItemOut
from app.services.invoices import quantity_decimal


def line_item_out(item) -> LineItemOut:
    return LineItemOut(
        id=item.id,
        description=item.description,
        quantity=quantity_decimal(item.quantity_milli),
        unit_price_cents=item.unit_price_cents,
        amount_cents=item.amount_cents,
    )


def invoice_out(invoice: Invoice) -> InvoiceOut:
    return InvoiceOut(
        id=invoice.id,
        number=invoice.number,
        status=invoice.status,
        currency=invoice.currency,
        client=invoice.client,
        items=[line_item_out(item) for item in invoice.items],
        subtotal_cents=invoice.subtotal_cents,
        discount_cents=invoice.discount_cents,
        tax_cents=invoice.tax_cents,
        total_cents=invoice.total_cents,
        notes=invoice.notes,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        paid_at=invoice.paid_at,
        share_token=invoice.share_token,
        share_expires_at=invoice.share_expires_at,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def invoice_summary(invoice: Invoice) -> InvoiceSummary:
    return InvoiceSummary(
        id=invoice.id,
        number=invoice.number,
        status=invoice.status,
        currency=invoice.currency,
        client_name=invoice.client.name,
        client_company=invoice.client.company,
        total_cents=invoice.total_cents,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        created_at=invoice.created_at,
    )


def _sum_for_status(db: Session, owner_id: str, status: str) -> int:
    total = db.execute(
        select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(
            Invoice.owner_id == owner_id,
            Invoice.status == status,
        )
    ).scalar_one()
    return int(total)


def outstanding_cents(db: Session, owner_id: str) -> int:
    return _sum_for_status(db, owner_id, InvoiceStatus.SENT)


def collected_cents(db: Session, owner_id: str) -> int:
    return _sum_for_status(db, owner_id, InvoiceStatus.PAID)
