"""Read access to effective-dated VAT rates."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.vat import VatRateCode
from app.modules.vat.models import VatRate


def rates_on(session: Session, on_date: date) -> Mapping[VatRateCode, Decimal]:
    """Return the applicable rate fraction for every VAT code on ``on_date``.

    For each code, selects the row where ``valid_from <= on_date`` and
    ``valid_to`` is null or ``valid_to >= on_date``. Raises :class:`LookupError`
    if any of the four codes has no applicable rate on that date — the invoice
    engine must never silently proceed with a missing rate.
    """
    stmt = select(VatRate.code, VatRate.rate).where(
        VatRate.valid_from <= on_date,
        or_(VatRate.valid_to.is_(None), VatRate.valid_to >= on_date),
    )
    found: dict[VatRateCode, Decimal] = {code: rate for code, rate in session.execute(stmt)}

    missing = [code for code in VatRateCode if code not in found]
    if missing:
        codes = ", ".join(code.value for code in missing)
        raise LookupError(f"No VAT rate effective on {on_date.isoformat()} for: {codes}")
    return found
