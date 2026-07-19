"""Invoice aggregate: the invoice header and its lines.

Drafts store **inputs only** — there are deliberately no computed money columns.
Totals are always computed on demand via ``app.core.vat.compute_totals``. At
issue (Phase 2) the seller, client, lines and rates are frozen into ``snapshot``
and a gapless ``number`` is allocated; issued invoices are then immutable.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.db import Base
from app.core.mixins import TimestampMixin
from app.core.money import reject_float
from app.core.vat import VatRateCode
from app.modules.vat.models import vat_rate_code_enum


class InvoiceStatus(StrEnum):
    """Lifecycle of an invoice. Numbers are allocated only at ``issued``."""

    draft = "draft"
    issued = "issued"
    void = "void"


invoice_status_enum = Enum(
    InvoiceStatus,
    name="invoice_status",
    values_callable=lambda enum: [member.value for member in enum],
)


class Invoice(TimestampMixin, Base):
    """An invoice header.

    ``number`` is null for drafts and allocated (gapless) only at issue; a
    partial unique index enforces uniqueness across issued invoices while
    permitting many null-numbered drafts. ``currency`` is GBP-only for the PoC.
    """

    __tablename__ = "invoice"
    __table_args__ = (
        CheckConstraint("currency = 'GBP'", name="ck_invoice_currency_gbp"),
        # Unique invoice numbers, but only among rows that have one (issued).
        Index(
            "uq_invoice_number",
            "number",
            unique=True,
            postgresql_where=text("number IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        invoice_status_enum,
        nullable=False,
        server_default=InvoiceStatus.draft.value,
    )
    number: Mapped[str | None] = mapped_column(Text, nullable=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False)

    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tax_point_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="GBP")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.position",
    )


class InvoiceLine(Base):
    """One line on an invoice. Inputs only — no computed money columns.

    The DB foreign key is a plain ``ON DELETE CASCADE`` so a draft can be
    deleted with its lines; the service layer restricts deletes to drafts only
    (issued invoices are never deleted).
    """

    __tablename__ = "invoice_line"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3, asdecimal=True), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4, asdecimal=True), nullable=False)
    vat_rate_code: Mapped[VatRateCode] = mapped_column(vat_rate_code_enum, nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")

    @validates("quantity", "unit_price")
    def _reject_float(self, key: str, value: object) -> object:
        # Floats must never touch money — reject at the model boundary, not just
        # downstream in round_money.
        return reject_float(key, value)
