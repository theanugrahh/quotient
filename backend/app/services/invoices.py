from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invoice, InvoiceItem, InvoiceStatus
from app.money import LineInput, compute_totals, line_amount_cents

_SEQUENCE = re.compile(r"INV-(\d+)")


def next_invoice_number(db: Session, owner_id: str) -> str:
    numbers = db.execute(
        select(Invoice.number).where(Invoice.owner_id == owner_id)
    ).scalars().all()
    highest = 0
    for number in numbers:
        match = _SEQUENCE.match(number)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"INV-{highest + 1:04d}"


def apply_line_items(
    invoice: Invoice,
    lines: list[tuple[str, int, int]],
) -> None:
    """Replace the invoice line items and recompute every monetary field."""
    invoice.items.clear()
    for position, (description, quantity_milli, unit_price_cents) in enumerate(lines):
        invoice.items.append(
            InvoiceItem(
                description=description,
                quantity_milli=quantity_milli,
                unit_price_cents=unit_price_cents,
                amount_cents=line_amount_cents(unit_price_cents, quantity_milli),
                position=position,
            )
        )

    totals = compute_totals(
        [LineInput(unit_price_cents=price, quantity_milli=qty) for _, qty, price in lines],
        tax_rate_bp=invoice.tax_rate_bp,
        discount_bp=invoice.discount_bp,
    )
    invoice.subtotal_cents = totals.subtotal_cents
    invoice.discount_cents = totals.discount_cents
    invoice.tax_cents = totals.tax_cents
    invoice.total_cents = totals.total_cents


def quantity_decimal(quantity_milli: int) -> Decimal:
    return Decimal(quantity_milli) / Decimal(1000)


def is_editable(invoice: Invoice) -> bool:
    return invoice.status == InvoiceStatus.DRAFT


def count_invoices(db: Session, owner_id: str | None = None) -> int:
    query = select(func.count()).select_from(Invoice)
    if owner_id:
        query = query.where(Invoice.owner_id == owner_id)
    return int(db.execute(query).scalar_one())
