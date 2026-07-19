"""DB tests for rates_on effective-dating."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.vat import VatRateCode
from app.modules.vat.models import VatRate
from app.modules.vat.repository import rates_on

BOUNDARY = date(2011, 1, 4)


def _seed_open_ended(session):
    """Seed the four current rates, open-ended from the boundary date."""
    session.add_all(
        [
            VatRate(code=VatRateCode.standard, rate=Decimal("0.2000"), valid_from=BOUNDARY),
            VatRate(code=VatRateCode.reduced, rate=Decimal("0.0500"), valid_from=BOUNDARY),
            VatRate(code=VatRateCode.zero, rate=Decimal("0.0000"), valid_from=BOUNDARY),
            VatRate(code=VatRateCode.exempt, rate=Decimal("0.0000"), valid_from=BOUNDARY),
        ]
    )
    session.flush()


def test_rates_on_boundary_date_returns_all_four(db_session):
    _seed_open_ended(db_session)
    rates = rates_on(db_session, BOUNDARY)
    assert set(rates) == set(VatRateCode)
    assert rates[VatRateCode.standard] == Decimal("0.2000")
    assert rates[VatRateCode.reduced] == Decimal("0.0500")


def test_rates_on_before_valid_from_raises(db_session):
    _seed_open_ended(db_session)
    with pytest.raises(LookupError):
        rates_on(db_session, date(2011, 1, 3))  # one day before any rate exists


def test_rates_on_picks_open_row_over_closed_out_row(db_session):
    # An older standard rate (17.5%) closed out the day before the boundary,
    # plus the current open-ended 20%. The other three codes are open-ended from
    # 2010-01-01 so that every code has an applicable rate on the earlier date.
    early = date(2010, 1, 1)
    db_session.add_all(
        [
            VatRate(
                code=VatRateCode.standard,
                rate=Decimal("0.1750"),
                valid_from=early,
                valid_to=date(2011, 1, 3),
            ),
            VatRate(code=VatRateCode.standard, rate=Decimal("0.2000"), valid_from=BOUNDARY),
            VatRate(code=VatRateCode.reduced, rate=Decimal("0.0500"), valid_from=early),
            VatRate(code=VatRateCode.zero, rate=Decimal("0.0000"), valid_from=early),
            VatRate(code=VatRateCode.exempt, rate=Decimal("0.0000"), valid_from=early),
        ]
    )
    db_session.flush()

    # Within the old range: the closed-out 17.5% applies.
    assert rates_on(db_session, date(2010, 6, 1))[VatRateCode.standard] == Decimal("0.1750")
    # On/after the boundary: the open-ended 20% applies.
    assert rates_on(db_session, BOUNDARY)[VatRateCode.standard] == Decimal("0.2000")
    assert rates_on(db_session, date(2026, 1, 1))[VatRateCode.standard] == Decimal("0.2000")


def test_rates_on_raises_after_a_code_is_fully_closed_out(db_session):
    # standard exists only up to 2011-01-03, then never again; the other codes
    # are open-ended. Asking on the boundary must raise because standard has no
    # applicable row.
    db_session.add_all(
        [
            VatRate(
                code=VatRateCode.standard,
                rate=Decimal("0.1750"),
                valid_from=date(2010, 1, 1),
                valid_to=date(2011, 1, 3),
            ),
            VatRate(code=VatRateCode.reduced, rate=Decimal("0.0500"), valid_from=BOUNDARY),
            VatRate(code=VatRateCode.zero, rate=Decimal("0.0000"), valid_from=BOUNDARY),
            VatRate(code=VatRateCode.exempt, rate=Decimal("0.0000"), valid_from=BOUNDARY),
        ]
    )
    db_session.flush()
    with pytest.raises(LookupError):
        rates_on(db_session, BOUNDARY)
