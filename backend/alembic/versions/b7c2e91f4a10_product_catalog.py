"""product catalog

Revision ID: b7c2e91f4a10
Revises: 57924f8aade2
Create Date: 2026-09-25 16:00:00.000000

Adds the per-user product & service catalog (Phase 5):

- ``product_kind`` enum and the ``product`` table (owner-scoped, UNIQUE
  (owner_id, code), CHECK unit_price >= 0, archive-not-delete);
- ``invoice_line.product_id`` — nullable FK (ON DELETE RESTRICT), so ad-hoc
  lines keep working and a draft can mix catalog and one-off lines;
- the catalog integrity triggers (product identity immutable, no product
  deletes, linked lines must match their product). The DDL is shared with the
  test harness via ``app.modules.products.integrity``.

Purely additive, so unlike 57924f8aade2 there is no empty-database guard:
existing lines simply get ``product_id = NULL`` (ad-hoc).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.modules.products.integrity import (
    PRODUCT_INTEGRITY_DOWN_SQL,
    PRODUCT_INTEGRITY_UP_SQL,
)

# revision identifiers, used by Alembic.
revision: str = "b7c2e91f4a10"
down_revision: str | Sequence[str] | None = "57924f8aade2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Created and dropped explicitly (create_type=False on the column type) so the
# downgrade removes the type too — see the Phase 1 enum round-trip fix.
product_kind = postgresql.ENUM("goods", "service", name="product_kind", create_type=False)
# Already exists (created in 5f7da3d0e4dd); referenced, never created here.
vat_rate_code = postgresql.ENUM(
    "standard", "reduced", "zero", "exempt", name="vat_rate_code", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    product_kind.create(bind, checkfirst=True)

    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", product_kind, nullable=False),
        sa.Column("vat_rate_code", vat_rate_code, nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_id", "code", name="uq_product_owner_code"),
        sa.CheckConstraint("unit_price >= 0", name="ck_product_unit_price_nonneg"),
    )
    op.create_index("ix_product_owner_id", "product", ["owner_id"])

    op.add_column("invoice_line", sa.Column("product_id", sa.Integer(), nullable=True))
    op.create_index("ix_invoice_line_product_id", "invoice_line", ["product_id"])
    op.create_foreign_key(
        "fk_invoice_line_product",
        "invoice_line",
        "product",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute(PRODUCT_INTEGRITY_UP_SQL)


def downgrade() -> None:
    op.execute(PRODUCT_INTEGRITY_DOWN_SQL)

    op.drop_constraint("fk_invoice_line_product", "invoice_line", type_="foreignkey")
    op.drop_index("ix_invoice_line_product_id", table_name="invoice_line")
    op.drop_column("invoice_line", "product_id")

    op.drop_index("ix_product_owner_id", table_name="product")
    op.drop_table("product")
    product_kind.drop(op.get_bind(), checkfirst=True)
