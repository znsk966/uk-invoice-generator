"""Unit tests for app.core.money — no database."""

from decimal import Decimal

import pytest

from app.core.money import TWO_PLACES, as_decimal, round_money


def test_round_money_classic_float_trap():
    # 2.675 is the textbook case: as a binary float it is slightly below 2.675
    # and rounds to 2.67, but the *decimal* value must round half-up to 2.68.
    assert round_money(Decimal("2.675")) == Decimal("2.68")


def test_round_money_rejects_float():
    # Floats must fail loudly rather than be silently converted.
    with pytest.raises(TypeError):
        round_money(2.675)


def test_round_money_rejects_bool():
    with pytest.raises(TypeError):
        round_money(True)


def test_round_money_half_up_boundary():
    assert round_money(Decimal("0.005")) == Decimal("0.01")
    assert round_money(Decimal("0.004")) == Decimal("0.00")


def test_round_money_negative_amounts():
    # ROUND_HALF_UP rounds away from zero at the .5 boundary for negatives too.
    assert round_money(Decimal("-2.675")) == Decimal("-2.68")
    assert round_money(Decimal("-0.005")) == Decimal("-0.01")


def test_round_money_already_quantized_is_stable():
    assert round_money(Decimal("10.00")) == Decimal("10.00")
    assert round_money(Decimal("10.00")).as_tuple().exponent == TWO_PLACES.as_tuple().exponent


def test_as_decimal_accepts_str_int_decimal():
    assert as_decimal("2.675") == Decimal("2.675")
    assert as_decimal(5) == Decimal("5")
    assert as_decimal(Decimal("3.14")) == Decimal("3.14")


def test_as_decimal_rejects_float_and_bool():
    with pytest.raises(TypeError):
        as_decimal(2.675)
    with pytest.raises(TypeError):
        as_decimal(True)
