"""immutability trigger for issued invoices and their lines

Revision ID: 14438b1216ca
Revises: de303147f0cb
Create Date: 2026-07-19 09:30:38.448490

Defense in depth for Project Law "issued invoices are immutable". The service
layer is the primary enforcement (status checks -> 409); these triggers are a
tripwire that fires even if a bug or a direct SQL statement bypasses the API.
The DDL lives in app.modules.invoices.immutability so the test harness applies
the exact same triggers it builds from metadata.
"""

from collections.abc import Sequence

from alembic import op
from app.modules.invoices.immutability import IMMUTABILITY_DOWN_SQL, IMMUTABILITY_UP_SQL

# revision identifiers, used by Alembic.
revision: str = "14438b1216ca"
down_revision: str | Sequence[str] | None = "de303147f0cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(IMMUTABILITY_UP_SQL)


def downgrade() -> None:
    op.execute(IMMUTABILITY_DOWN_SQL)
