"""schema: company, clients, vat rates, invoices, numbering

Revision ID: 5f7da3d0e4dd
Revises:
Create Date: 2026-07-19 08:14:24.386993

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f7da3d0e4dd"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Postgres ENUM types are created and dropped explicitly (create_type=False on
# the columns) so that: (a) the type shared by vat_rate and invoice_line is
# created exactly once, and (b) downgrade removes the types too, leaving the
# database truly empty and the upgrade/downgrade cycle repeatable.
vat_rate_code = postgresql.ENUM(
    "standard", "reduced", "zero", "exempt", name="vat_rate_code", create_type=False
)
invoice_status = postgresql.ENUM(
    "draft", "issued", "void", name="invoice_status", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    vat_rate_code.create(bind, checkfirst=True)
    invoice_status.create(bind, checkfirst=True)

    op.create_table(
        "client",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("postcode", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=2), server_default="GB", nullable=False),
        sa.Column("vat_number", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
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
    )
    op.create_table(
        "company_profile",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("trading_name", sa.String(length=255), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("postcode", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=2), server_default="GB", nullable=False),
        sa.Column("vat_number", sa.String(length=32), nullable=True),
        sa.Column("company_number", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("bank_account_name", sa.String(length=255), nullable=True),
        sa.Column("bank_sort_code", sa.String(length=16), nullable=True),
        sa.Column("bank_account_number", sa.String(length=32), nullable=True),
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
        sa.CheckConstraint("id = 1", name="ck_company_profile_single_row"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "number_sequence",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("next_value", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "vat_rate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", vat_rate_code, nullable=False),
        sa.Column("rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "valid_from", name="uq_vat_rate_code_valid_from"),
    )
    op.create_table(
        "invoice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", invoice_status, server_default="draft", nullable=False),
        sa.Column("number", sa.Text(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("tax_point_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.Text(), server_default="GBP", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("currency = 'GBP'", name="ck_invoice_currency_gbp"),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_invoice_number",
        "invoice",
        ["number"],
        unique=True,
        postgresql_where=sa.text("number IS NOT NULL"),
    )
    op.create_table(
        "invoice_line",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("vat_rate_code", vat_rate_code, nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoice.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("invoice_line")
    op.drop_index(
        "uq_invoice_number", table_name="invoice", postgresql_where=sa.text("number IS NOT NULL")
    )
    op.drop_table("invoice")
    op.drop_table("vat_rate")
    op.drop_table("number_sequence")
    op.drop_table("company_profile")
    op.drop_table("client")

    bind = op.get_bind()
    invoice_status.drop(bind, checkfirst=True)
    vat_rate_code.drop(bind, checkfirst=True)
