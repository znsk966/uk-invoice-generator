"""Fixtures for the API integration tier.

These tests drive the real ASGI app over httpx, so they need *real* commits
(gapless numbering across two issues, the immutability trigger firing on
committed rows). Isolation is therefore by truncation, not transaction rollback:
before and after each test every mutable table is truncated and the four UK VAT
rates are re-seeded. ``vat_rate`` is truncated too so the DB tier (which manages
its own rate rows) sees an empty table.

The ``get_session`` dependency is overridden to bind to the *test* engine
(``db_engine`` from the root conftest, on TEST_DATABASE_URL) rather than the
app's configured DATABASE_URL — API tests must never touch the dev database.
"""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_session
from app.core.vat import VatRateCode
from app.main import create_app

_MUTABLE_TABLES = (
    "invoice_line",
    "invoice",
    "client",
    "company_profile",
    "number_sequence",
    "vat_rate",
)

# The Phase 1 seed: current UK rates, open-ended from 2011-01-04.
_SEED_FROM = date(2011, 1, 4)
_SEED_RATES = {
    VatRateCode.standard: Decimal("0.2000"),
    VatRateCode.reduced: Decimal("0.0500"),
    VatRateCode.zero: Decimal("0.0000"),
    VatRateCode.exempt: Decimal("0.0000"),
}


def _truncate(db_engine) -> None:
    with db_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(_MUTABLE_TABLES)} RESTART IDENTITY CASCADE"))


def _seed_rates(db_engine) -> None:
    with db_engine.begin() as conn:
        for code, rate in _SEED_RATES.items():
            conn.execute(
                text(
                    "INSERT INTO vat_rate (code, rate, valid_from, valid_to) "
                    "VALUES (:code, :rate, :valid_from, NULL)"
                ),
                {"code": code.value, "rate": rate, "valid_from": _SEED_FROM},
            )


@pytest.fixture(autouse=True)
def _clean_db(db_engine) -> Iterator[None]:
    # Fresh slate + rates for this test. Teardown truncates only (no re-seed), so
    # the DB tier — which manages its own vat_rate rows — sees an empty table.
    _truncate(db_engine)
    _seed_rates(db_engine)
    yield
    _truncate(db_engine)


@pytest.fixture
def client(db_engine) -> Iterator[TestClient]:
    TestSession = sessionmaker(bind=db_engine, autoflush=False)

    def _override_get_session() -> Iterator[Session]:
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_engine_for_test(db_engine):
    """Expose the raw test engine to tests that bypass the API on purpose
    (e.g. asserting the immutability trigger fires on a direct SQL UPDATE)."""
    return db_engine
