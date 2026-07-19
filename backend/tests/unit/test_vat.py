"""Unit tests for app.core.vat — no database.

These pin down the money-critical behaviour: per-rate-group rounding, group
ordering, and zero vs exempt staying distinct.
"""

from decimal import Decimal

from app.core.vat import (
    InvoiceTotals,
    LineInput,
    VatRateCode,
    compute_totals,
)

# Full rate table used by most tests.
RATES = {
    VatRateCode.standard: Decimal("0.20"),
    VatRateCode.reduced: Decimal("0.05"),
    VatRateCode.zero: Decimal("0"),
    VatRateCode.exempt: Decimal("0"),
}


def test_per_group_rounding_differs_from_per_line():
    # Nine lines of £0.03 at 20%.
    #   Per-line (WRONG): round(0.03 * 0.20) = round(0.006) = 0.01 each,
    #     summed over 9 lines -> VAT of 0.09.
    #   Per-group (CORRECT): net = 9 * 0.03 = 0.27; VAT = round(0.27 * 0.20)
    #     = round(0.054) = 0.05.
    # The engine must produce 0.05, not 0.09.
    lines = [LineInput(Decimal("1"), Decimal("0.03"), VatRateCode.standard) for _ in range(9)]
    totals = compute_totals(lines, RATES)

    per_line_vat = sum(
        (Decimal("0.01") for _ in range(9)), start=Decimal("0")
    )  # 0.09, the wrong answer
    assert per_line_vat == Decimal("0.09")

    (group,) = totals.groups
    assert group.net == Decimal("0.27")
    assert group.vat == Decimal("0.05")  # per-group, and != 0.09
    assert group.gross == Decimal("0.32")
    assert totals.total_vat == Decimal("0.05")


def test_mixed_group_invoice_ordering_and_totals():
    lines = [
        LineInput(Decimal("2"), Decimal("10.00"), VatRateCode.standard),  # net 20.00
        LineInput(Decimal("1"), Decimal("10.00"), VatRateCode.reduced),  # net 10.00
        LineInput(Decimal("3"), Decimal("5.00"), VatRateCode.zero),  # net 15.00
        LineInput(Decimal("1"), Decimal("4.00"), VatRateCode.exempt),  # net 4.00
    ]
    totals = compute_totals(lines, RATES)

    # Groups appear in canonical order: standard, reduced, zero, exempt.
    assert [g.code for g in totals.groups] == [
        VatRateCode.standard,
        VatRateCode.reduced,
        VatRateCode.zero,
        VatRateCode.exempt,
    ]
    standard, reduced, zero, exempt = totals.groups
    assert (standard.net, standard.vat) == (Decimal("20.00"), Decimal("4.00"))
    assert (reduced.net, reduced.vat) == (Decimal("10.00"), Decimal("0.50"))
    assert (zero.net, zero.vat) == (Decimal("15.00"), Decimal("0.00"))
    assert (exempt.net, exempt.vat) == (Decimal("4.00"), Decimal("0.00"))

    assert totals.total_net == Decimal("49.00")
    assert totals.total_vat == Decimal("4.50")
    assert totals.total_gross == Decimal("53.50")


def test_empty_invoice_is_zeroed_with_no_groups():
    totals = compute_totals([], RATES)
    assert isinstance(totals, InvoiceTotals)
    assert totals.groups == ()
    assert totals.total_net == Decimal("0")
    assert totals.total_vat == Decimal("0")
    assert totals.total_gross == Decimal("0")


def test_zero_and_exempt_are_distinct_groups():
    lines = [
        LineInput(Decimal("1"), Decimal("10.00"), VatRateCode.zero),
        LineInput(Decimal("1"), Decimal("7.00"), VatRateCode.exempt),
    ]
    totals = compute_totals(lines, RATES)
    codes = [g.code for g in totals.groups]
    assert codes == [VatRateCode.zero, VatRateCode.exempt]
    assert len(totals.groups) == 2  # not merged, even though both rate to 0


def test_line_net_is_rounded_before_grouping():
    # quantity * unit_price with sub-penny precision rounds per line first.
    # 3 * 1.005 = 3.015 -> round_money -> 3.02 (half up).
    lines = [LineInput(Decimal("3"), Decimal("1.005"), VatRateCode.standard)]
    totals = compute_totals(lines, RATES)
    (group,) = totals.groups
    assert group.net == Decimal("3.02")
    assert group.vat == Decimal("0.60")  # round(3.02 * 0.20) = round(0.604)
