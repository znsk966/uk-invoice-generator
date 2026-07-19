"""Money primitives for the invoice generator.

Project Law (see CLAUDE.md): all money is :class:`~decimal.Decimal` with
``ROUND_HALF_UP``. Floats never touch money — they are rejected loudly rather
than silently converted, because binary floats cannot represent decimal cents
exactly (the classic ``2.675`` trap rounds the wrong way).

GBP only for the PoC.

Numeric precision conventions (used by every model column and honoured here):

* money amounts  -> ``Numeric(12, 2)`` — 2 decimal places (pence).
* unit prices    -> ``Numeric(12, 4)`` — 4 decimal places, so per-unit prices
  can carry sub-penny precision before a line is rounded to money.
* quantities     -> ``Numeric(12, 3)`` — 3 decimal places.

Rounding happens at well-defined points only (see ``vat.py``): a line's money
value is ``round_money(quantity * unit_price)``, and VAT is rounded once per
rate group. Intermediate products are kept exact until such a point.
"""

from decimal import ROUND_HALF_UP, Decimal

# The quantization exponent for money: two decimal places (pence).
TWO_PLACES = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    """Quantize a Decimal to 2 decimal places using ROUND_HALF_UP.

    Only accepts :class:`~decimal.Decimal`. A ``float`` (or any non-Decimal)
    raises :class:`TypeError` — floats must fail loudly, never be coerced, so
    that a float can never leak into a money path unnoticed.
    """
    # bool is a subclass of int, but neither is a Decimal — reject everything
    # that is not exactly a Decimal.
    if not isinstance(value, Decimal):
        raise TypeError(f"round_money requires Decimal, got {type(value).__name__}")
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def as_decimal(value: str | int | Decimal) -> Decimal:
    """Safely construct a Decimal from a str, int, or Decimal.

    Explicitly rejects ``float`` (and ``bool``, an int subclass) with
    :class:`TypeError`: constructing ``Decimal`` from a float would import the
    float's binary rounding error into the money system.
    """
    if isinstance(value, bool):
        raise TypeError("as_decimal does not accept bool")
    if isinstance(value, float):
        raise TypeError(
            "as_decimal does not accept float — floats must never touch money; "
            "pass a str like '2.675' or a Decimal instead"
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int)):
        return Decimal(value)
    raise TypeError(f"as_decimal cannot handle {type(value).__name__}")
