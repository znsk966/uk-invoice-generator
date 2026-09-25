"""Auth models: ``User`` and ``UserSession``.

A session is an opaque random token handed to the client in an HTTP-only cookie.
We store only its SHA-256 hash (``token_hash``), never the token itself — so a
database leak cannot be replayed as a live session. See ``security.py`` for the
token/hashing primitives.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class User(Base):
    """A registered user. Email is unique and always stored lowercased."""

    __tablename__ = "user"
    # Named explicitly (matching the migration) so the test schema built from
    # metadata and the migrated schema agree: ``register`` maps a violation of
    # this exact constraint to 409 ``email_taken``.
    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    """A live login session.

    The primary key is the SHA-256 hash of the cookie token, so a lookup is a
    single indexed hit on the hash we can recompute from the incoming cookie.
    ``expires_at`` is checked on every request; ``logout`` deletes the row for
    real server-side revocation (not just clearing the cookie).
    """

    __tablename__ = "user_session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")
