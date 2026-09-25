"""Product & service catalog: per-user master data for invoice lines.

A product's **identity is immutable**: once created, its ``code``,
``description``, ``kind`` and ``vat_rate_code`` never change (a DB trigger in
``integrity.py`` enforces this). To change any of them, archive the product and
create a new one. Only ``unit_price`` — the default price for *new* lines — is
editable, and changing it never touches existing lines.

Because identity is immutable, an invoice line linked to a product can safely
carry copies of the product's description and VAT rate: they can never drift.
Archive, never delete (Project Law rule 5), so linked lines keep valid refs.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.db import Base
from app.core.mixins import TimestampMixin
from app.core.money import reject_float
from app.core.vat import VatRateCode
from app.modules.vat.models import vat_rate_code_enum


class ProductKind(StrEnum):
    """Goods or services. Recorded now because UK tax-point rules differ."""

    goods = "goods"
    service = "service"


product_kind_enum = Enum(
    ProductKind,
    name="product_kind",
    values_callable=lambda enum: [member.value for member in enum],
)


class Product(TimestampMixin, Base):
    """One catalog entry, owned by exactly one user (Project Law rule 9)."""

    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("owner_id", "code", name="uq_product_owner_code"),
        CheckConstraint("unit_price >= 0", name="ck_product_unit_price_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Identity — immutable after insert (enforced by trg_product_identity).
    code: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[ProductKind] = mapped_column(product_kind_enum, nullable=False)
    vat_rate_code: Mapped[VatRateCode] = mapped_column(vat_rate_code_enum, nullable=False)

    # The one mutable field: the default price pre-filled on new lines.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4, asdecimal=True), nullable=False)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @validates("unit_price")
    def _reject_float(self, key: str, value: object) -> object:
        # Floats must never touch money — same model-boundary guard as lines.
        return reject_float(key, value)
