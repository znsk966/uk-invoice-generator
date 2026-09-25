"""Persistent counters backing gapless invoice numbering."""

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NumberSequence(Base):
    """A named integer counter, **per owner**. ``next_value`` is the value the
    next allocation will return (then incremented), under row-level locking —
    see ``app.core.numbering.allocate_number``.

    The primary key is composite ``(owner_id, key)``: each user has their own
    independent sequence for a given key, so their invoice numbers never
    collide with or gap around another user's.
    """

    __tablename__ = "number_sequence"

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), primary_key=True
    )
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
