"""VAT engine — pure, no database access.

This module owns the one piece of arithmetic the whole product hinges on:
turning invoice line inputs into per-rate-group and invoice-level totals.

Project Law (see CLAUDE.md): VAT is rounded **per rate group**, on the group
net — never per line. Rounding per line and summing would drift by a penny or
more on invoices with many small lines; the documented divergence is exercised
in the tests.

The returned :class:`InvoiceTotals` structure is deliberately the shape the API
(Phase 2) and the PDF (Phase 4) will render, so it is fixed now.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.core.money import round_money


class VatRateCode(StrEnum):
    """The four UK VAT treatments relevant to the PoC.

    ``zero`` and ``exempt`` both carry a rate of 0 but are legally distinct and
    must appear as separate groups on an invoice, so they are separate codes.
    """

    standard = "standard"
    reduced = "reduced"
    zero = "zero"
    exempt = "exempt"


# The order groups must appear in on every invoice / breakdown.
_GROUP_ORDER: tuple[VatRateCode, ...] = (
    VatRateCode.standard,
    VatRateCode.reduced,
    VatRateCode.zero,
    VatRateCode.exempt,
)


@dataclass(frozen=True)
class LineInput:
    """One invoice line's raw inputs. No money is computed until compute_totals."""

    quantity: Decimal
    unit_price: Decimal
    vat_rate_code: VatRateCode


@dataclass(frozen=True)
class RateGroup:
    """Totals for all lines sharing a single VAT rate code."""

    code: VatRateCode
    rate: Decimal
    net: Decimal
    vat: Decimal
    gross: Decimal


@dataclass(frozen=True)
class InvoiceTotals:
    """The complete money breakdown for an invoice.

    ``groups`` is ordered standard -> reduced -> zero -> exempt, and contains
    only the groups that actually have lines. The invoice-level totals are the
    sums of the group values.
    """

    groups: tuple[RateGroup, ...]
    total_net: Decimal
    total_vat: Decimal
    total_gross: Decimal


def compute_totals(
    lines: Sequence[LineInput],
    rates: Mapping[VatRateCode, Decimal],
) -> InvoiceTotals:
    """Compute per-group and invoice-level totals from line inputs.

    ``rates`` maps each VAT code to its rate as a fraction (e.g.
    ``Decimal("0.20")`` for standard). Every code used by a line must be
    present in ``rates`` or :class:`KeyError` is raised.

    Algorithm, in exactly this order (Project Law):

    1. line net = ``round_money(quantity * unit_price)`` per line (2 dp).
    2. group lines by ``vat_rate_code``; per group ``net = sum(line nets)`` and
       ``vat = round_money(net * rate)`` — VAT computed once on the group net.
    3. ``gross = net + vat`` per group; invoice totals are the sums of the
       group values.

    An empty ``lines`` yields zeroed totals and no groups.
    """
    # Step 1 + accumulate step 2's group nets, preserving nothing but the sum.
    group_nets: dict[VatRateCode, Decimal] = {}
    for line in lines:
        line_net = round_money(line.quantity * line.unit_price)
        group_nets[line.vat_rate_code] = group_nets.get(line.vat_rate_code, Decimal("0")) + line_net

    # Steps 2 (vat) + 3, emitting groups in the canonical order.
    groups: list[RateGroup] = []
    total_net = Decimal("0.00")
    total_vat = Decimal("0.00")
    total_gross = Decimal("0.00")
    for code in _GROUP_ORDER:
        if code not in group_nets:
            continue
        rate = rates[code]
        net = group_nets[code]
        vat = round_money(net * rate)
        gross = net + vat
        groups.append(RateGroup(code=code, rate=rate, net=net, vat=vat, gross=gross))
        total_net += net
        total_vat += vat
        total_gross += gross

    return InvoiceTotals(
        groups=tuple(groups),
        total_net=total_net,
        total_vat=total_vat,
        total_gross=total_gross,
    )
