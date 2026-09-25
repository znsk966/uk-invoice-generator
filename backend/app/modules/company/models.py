"""The seller's own company profile — a single-row table."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.mixins import TimestampMixin


class CompanyProfile(TimestampMixin, Base):
    """The trading entity issuing invoices.

    One profile **per user**: ``UNIQUE (owner_id)`` makes it a singleton within
    an account (the old global ``CHECK (id = 1)`` singleton is gone now that the
    app is multi-user). VAT and company numbers are nullable — not every
    business is VAT-registered or incorporated. Bank details are nullable too.
    """

    __tablename__ = "company_profile"
    __table_args__ = (UniqueConstraint("owner_id", name="uq_company_profile_owner"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # No index=True: the UNIQUE(owner_id) constraint above already indexes it.
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False
    )

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
