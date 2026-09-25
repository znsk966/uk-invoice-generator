"""Client (bill-to) master data. Archive, never hard-delete."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.mixins import TimestampMixin


class Client(TimestampMixin, Base):
    """A customer the seller invoices.

    Project Law: master data is archived, never hard-deleted, so issued
    invoices keep a valid reference. ``archived_at`` being non-null marks a
    client as archived; there is no DELETE path anywhere in this codebase.

    Owned per user (``owner_id``): a client belongs to exactly one account and
    is only ever reachable through queries scoped to that owner.
    """

    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    postcode: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, server_default="GB")

    vat_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
