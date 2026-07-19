"""Unit tests for the float-rejection guard on money columns — no database.

SQLAlchemy ``@validates`` hooks fire on Python-side attribute assignment (incl.
during ``__init__``), so these need no session or database connection.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.money import reject_float
from app.core.vat import VatRateCode
from app.modules.invoices.models import InvoiceLine
from app.modules.vat.models import VatRate


def test_reject_float_helper():
    assert reject_float("x", Decimal("1.5")) == Decimal("1.5")
    assert reject_float("x", 3) == 3
    assert reject_float("x", "1.5") == "1.5"
    assert reject_float("x", None) is None
    with pytest.raises(TypeError):
        reject_float("x", 0.1)
    with pytest.raises(TypeError):
        reject_float("x", True)


def test_invoice_line_rejects_float_unit_price_on_assignment():
    line = InvoiceLine(
        position=1,
        description="x",
        quantity=Decimal("1"),
        unit_price=Decimal("0.10"),
        vat_rate_code=VatRateCode.standard,
    )
    with pytest.raises(TypeError):
        line.unit_price = 0.1


def test_invoice_line_rejects_float_in_constructor():
    with pytest.raises(TypeError):
        InvoiceLine(
            position=1,
            description="x",
            quantity=Decimal("1"),
            unit_price=0.1,  # float backdoor — must be rejected at the boundary
            vat_rate_code=VatRateCode.standard,
        )


def test_invoice_line_rejects_float_quantity():
    with pytest.raises(TypeError):
        InvoiceLine(
            position=1,
            description="x",
            quantity=1.0,
            unit_price=Decimal("0.10"),
            vat_rate_code=VatRateCode.standard,
        )


def test_invoice_line_accepts_decimal():
    line = InvoiceLine(
        position=1,
        description="x",
        quantity=Decimal("2.500"),
        unit_price=Decimal("1.2345"),
        vat_rate_code=VatRateCode.standard,
    )
    assert line.quantity == Decimal("2.500")
    assert line.unit_price == Decimal("1.2345")


def test_vat_rate_rejects_float_rate():
    with pytest.raises(TypeError):
        VatRate(code=VatRateCode.standard, rate=0.2, valid_from=date(2011, 1, 4))


def test_vat_rate_accepts_decimal_rate():
    rate = VatRate(code=VatRateCode.standard, rate=Decimal("0.2000"), valid_from=date(2011, 1, 4))
    assert rate.rate == Decimal("0.2000")
