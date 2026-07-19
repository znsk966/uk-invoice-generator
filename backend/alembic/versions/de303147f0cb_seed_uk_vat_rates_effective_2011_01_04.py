"""seed: UK VAT rates effective 2011-01-04

Revision ID: de303147f0cb
Revises: 5f7da3d0e4dd
Create Date: 2026-07-19 08:17:21.348724

Seeds the current UK VAT rates as open-ended reference data, effective from
2011-01-04 (the date the standard rate rose to 20%). Rates are stored as
fractions. zero and exempt both carry 0 but remain distinct codes.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de303147f0cb"
down_revision: str | Sequence[str] | None = "5f7da3d0e4dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# A lightweight table reference for bulk insert/delete (no ORM dependency).
_vat_rate = sa.table(
    "vat_rate",
    sa.column("code", sa.Enum("standard", "reduced", "zero", "exempt", name="vat_rate_code")),
    sa.column("rate", sa.Numeric(5, 4)),
    sa.column("valid_from", sa.Date()),
    sa.column("valid_to", sa.Date()),
)

_VALID_FROM = "2011-01-04"
_SEED = [
    {"code": "standard", "rate": "0.2000", "valid_from": _VALID_FROM, "valid_to": None},
    {"code": "reduced", "rate": "0.0500", "valid_from": _VALID_FROM, "valid_to": None},
    {"code": "zero", "rate": "0.0000", "valid_from": _VALID_FROM, "valid_to": None},
    {"code": "exempt", "rate": "0.0000", "valid_from": _VALID_FROM, "valid_to": None},
]


def upgrade() -> None:
    """Insert the seed VAT rates."""
    op.bulk_insert(_vat_rate, _SEED)


def downgrade() -> None:
    """Remove exactly the seeded rows."""
    op.execute(
        sa.delete(_vat_rate).where(
            _vat_rate.c.code.in_(["standard", "reduced", "zero", "exempt"]),
            _vat_rate.c.valid_from == sa.text(f"'{_VALID_FROM}'"),
        )
    )
