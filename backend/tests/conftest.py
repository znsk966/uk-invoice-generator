"""Shared DB fixtures for every DB-touching test tier.

Reads TEST_DATABASE_URL from the environment. If it is unset, every DB test is
skipped with a clear message — we never run destructive CREATE/DROP TABLE
against the app's DATABASE_URL. In CI, TEST_DATABASE_URL points at the
throwaway ``uk_invoice_test`` service database.

The schema is built once per session from the models' metadata, plus the exact
same immutability triggers the Alembic migration installs (imported from
app.modules.invoices.immutability so the two never drift). It is torn down at
session end.

Isolation strategy differs by tier and is provided by the per-tier conftests:
- DB tier (``tests/db``): ``db_session`` wraps each test in a rolled-back
  transaction; committing tests take ``session_factory``.
- API tier (``tests/api``): real commits through the app, with a per-test
  truncate + rate re-seed (see ``tests/api/conftest.py``).
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base  # imported for the side effect of populating metadata
from app.modules.invoices.immutability import IMMUTABILITY_DOWN_SQL, IMMUTABILITY_UP_SQL

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def db_engine():
    if not TEST_DATABASE_URL:
        pytest.skip(
            "TEST_DATABASE_URL is not set — skipping DB tests. Set it to a "
            "throwaway database (e.g. uk_invoice_test) to run this tier."
        )
    engine = create_engine(TEST_DATABASE_URL)
    # Start from a clean slate even if a previous run left objects behind.
    with engine.begin() as conn:
        conn.execute(text(IMMUTABILITY_DOWN_SQL))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(IMMUTABILITY_UP_SQL))
    try:
        yield engine
    finally:
        with engine.begin() as conn:
            conn.execute(text(IMMUTABILITY_DOWN_SQL))
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """A session wrapped in a transaction that is always rolled back."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def session_factory(db_engine):
    """A plain sessionmaker for tests that need their own committing sessions."""
    return sessionmaker(bind=db_engine)
