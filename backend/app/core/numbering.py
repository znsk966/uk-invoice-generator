"""Gapless sequential numbering.

Project Law: invoice numbers are gapless and allocated only at the moment of
issue, inside a transaction. UK law requires invoice numbers to be unique and
sequential; per-year sequences satisfy this while allowing a clean annual reset.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.numbering.models import NumberSequence


def allocate_number(session: Session, key: str) -> int:
    """Allocate and return the next integer for ``key``, gaplessly.

    Locks the ``number_sequence`` row with ``SELECT ... FOR UPDATE`` (creating
    it on first use), returns its current ``next_value``, and increments it.

    **Transaction contract:** this MUST run inside the caller's transaction and
    the caller MUST NOT commit until the allocated number is safely persisted
    (e.g. written onto the issued invoice). Because the increment lives in the
    same transaction as the work that consumes the number, a rollback un-does
    the increment too — so a rolled-back issue never burns a number, and the
    next issue reuses it. The row-level lock serialises concurrent allocators on
    the same key, guaranteeing no duplicate and no gap.

    Postgres-only by design: the create-if-missing step uses ``INSERT ... ON
    CONFLICT DO NOTHING``. Do not "portablise" this into a plain SELECT-then-
    INSERT, which would reintroduce the create race this deliberately closes.
    The whole project targets PostgreSQL only.
    """
    # Ensure the row exists without racing concurrent creators: an idempotent
    # upsert that does nothing if another transaction already created it.
    session.execute(
        pg_insert(NumberSequence)
        .values(key=key, next_value=1)
        .on_conflict_do_nothing(index_elements=[NumberSequence.key])
    )

    row = session.execute(
        select(NumberSequence).where(NumberSequence.key == key).with_for_update()
    ).scalar_one()

    value = row.next_value
    row.next_value = value + 1
    session.flush()
    return value


def format_invoice_number(year: int, seq: int) -> str:
    """Render an invoice number as ``INV-{year}-{seq:05d}`` (e.g. INV-2026-00007)."""
    return f"INV-{year}-{seq:05d}"


def invoice_sequence_key(year: int) -> str:
    """The number_sequence key for a given year's invoices (per-year reset)."""
    return f"invoice-{year}"
