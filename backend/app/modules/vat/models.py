"""Effective-dated UK VAT reference data.

Project Law: VAT rates are effective-dated reference data — never hardcoded in
business logic. Rows are seeded by migration and read via ``rates_on``.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.vat import VatRateCode

# A single shared Enum type object (Postgres type ``vat_rate_code``), reused by
# both vat_rate.code and invoice_line.vat_rate_code so the DB type is defined
# once. values_callable stores the enum *values* (lowercase), not member repr.
vat_rate_code_enum = Enum(
    VatRateCode,
    name="vat_rate_code",
    values_callable=lambda enum: [member.value for member in enum],
)


class VatRate(Base):
    """One VAT rate for one code, effective over a half-open date range.

    ``rate`` is stored as a fraction (e.g. 0.2000 for 20%) in Numeric(5, 4).
    A row applies on ``d`` when ``valid_from <= d`` and ``valid_to`` is null or
    ``valid_to >= d``. ``(code, valid_from)`` is unique.
    """

    __tablename__ = "vat_rate"
    __table_args__ = (UniqueConstraint("code", "valid_from", name="uq_vat_rate_code_valid_from"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[VatRateCode] = mapped_column(vat_rate_code_enum, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4, asdecimal=True), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
