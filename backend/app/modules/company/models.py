"""The seller's own company profile — a single-row table."""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.mixins import TimestampMixin


class CompanyProfile(TimestampMixin, Base):
    """The trading entity issuing invoices.

    Enforced single row: ``id`` is a plain integer PK constrained to ``1``.
    VAT and company numbers are nullable — not every business is VAT-registered
    or incorporated. Bank details are nullable too.
    """

    __tablename__ = "company_profile"
    __table_args__ = (CheckConstraint("id = 1", name="ck_company_profile_single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)

    trading_name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    postcode: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, server_default="GB")

    vat_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    bank_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_sort_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
