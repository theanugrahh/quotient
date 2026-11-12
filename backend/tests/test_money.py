from __future__ import annotations

from app.money import LineInput, compute_totals, format_money, line_amount_cents


def test_line_amount_handles_fractional_quantities() -> None:
    assert line_amount_cents(15000, 10_000) == 150_000
    assert line_amount_cents(4000, 2_500) == 10_000
    assert line_amount_cents(333, 1_500) == 500
    assert line_amount_cents(0, 1_000) == 0


def test_line_amount_rounds_half_up() -> None:
    assert line_amount_cents(1, 500) == 1
    assert line_amount_cents(3, 500) == 2


def test_line_amount_rejects_invalid_input() -> None:
    for bad in [(1000, 0), (1000, -5)]:
        try:
            line_amount_cents(*bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_totals_apply_discount_before_tax() -> None:
    lines = [LineInput(unit_price_cents=15000, quantity_milli=10_000)]
    totals = compute_totals(lines, tax_rate_bp=1000, discount_bp=500)
    assert totals.subtotal_cents == 150_000
    assert totals.discount_cents == 7_500
    assert totals.tax_cents == 14_250
    assert totals.total_cents == 156_750


def test_totals_without_tax_or_discount() -> None:
    totals = compute_totals([LineInput(unit_price_cents=2500, quantity_milli=4_000)])
    assert totals.subtotal_cents == 10_000
    assert totals.discount_cents == 0
    assert totals.tax_cents == 0
    assert totals.total_cents == 10_000


def test_totals_reject_out_of_range_rates() -> None:
    for kwargs in ({"tax_rate_bp": 10_001}, {"discount_bp": -1}):
        try:
            compute_totals([], **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {kwargs}")


def test_format_money() -> None:
    assert format_money(156_750, "usd") == "$1,567.50"
    assert format_money(0, "usd") == "$0.00"
