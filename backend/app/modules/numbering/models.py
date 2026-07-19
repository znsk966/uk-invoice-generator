"""Persistent counters backing gapless invoice numbering."""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NumberSequence(Base):
    """A named integer counter. ``next_value`` is the value the next allocation
    will return (then incremented), under row-level locking — see
    ``app.core.numbering.allocate_number``.
    """

    __tablename__ = "number_sequence"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
