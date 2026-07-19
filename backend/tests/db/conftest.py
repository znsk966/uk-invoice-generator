"""Fixtures for the DB test tier.

Reads TEST_DATABASE_URL from the environment. If it is unset, every DB test is
skipped with a clear message — we never run destructive CREATE/DROP TABLE
against the app's DATABASE_URL. In CI, TEST_DATABASE_URL points at the
throwaway ``uk_invoice_test`` service database.

The schema is created once per test session (from the models' metadata, not via
migrations) and dropped at the end. Each test that uses ``db_session`` runs
inside a transaction that is rolled back on teardown, keeping tests isolated.
Tests that genuinely need independent, committing transactions (concurrency,
rollback-reuse) take ``db_engine`` and manage their own sessions.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base  # imported for the side effect of populating metadata

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def db_engine():
    if not TEST_DATABASE_URL:
        pytest.skip(
            "TEST_DATABASE_URL is not set — skipping DB tests. Set it to a "
            "throwaway database (e.g. uk_invoice_test) to run this tier."
        )
    engine = create_engine(TEST_DATABASE_URL)
    # Start from a clean slate even if a previous run left tables/types behind.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
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
