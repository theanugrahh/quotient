from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MILLI = Decimal("1000")


@dataclass(frozen=True)
class LineInput:
    unit_price_cents: int
    quantity_milli: int


@dataclass(frozen=True)
class Totals:
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int


def line_amount_cents(unit_price_cents: int, quantity_milli: int) -> int:
    """Convert a unit price and thousandths-of-a-unit quantity into an exact cent amount."""
    if quantity_milli <= 0:
        raise ValueError("Quantity must be greater than zero.")
    if unit_price_cents < 0:
        raise ValueError("Unit price cannot be negative.")
    product = Decimal(unit_price_cents) * Decimal(quantity_milli)
    return int((product / MILLI).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_totals(
    lines: list[LineInput],
    *,
    tax_rate_bp: int = 0,
    discount_bp: int = 0,
) -> Totals:
    """Derive invoice totals from line items. Client supplied totals are never trusted."""
    if tax_rate_bp < 0 or tax_rate_bp > 10_000:
        raise ValueError("Tax rate must be between 0 and 10000 basis points.")
    if discount_bp < 0 or discount_bp > 10_000:
        raise ValueError("Discount must be between 0 and 10000 basis points.")

    subtotal = sum(line_amount_cents(line.unit_price_cents, line.quantity_milli) for line in lines)

    discount = int(
        (Decimal(subtotal) * Decimal(discount_bp) / Decimal(10_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    taxable = subtotal - discount
    tax = int(
        (Decimal(taxable) * Decimal(tax_rate_bp) / Decimal(10_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return Totals(
        subtotal_cents=subtotal,
        discount_cents=discount,
        tax_cents=tax,
        total_cents=taxable + tax,
    )


def format_money(amount_cents: int, currency: str = "usd") -> str:
    symbol = {"usd": "$", "eur": "€", "gbp": "£", "inr": "₹"}.get(currency.lower(), "")
    amount = Decimal(amount_cents) / Decimal(100)
    if symbol:
        return f"{symbol}{amount:,.2f}"
    return f"{amount:,.2f} {currency.upper()}"
