"""Auth service: registration, login, session creation/lookup, logout.

Runs inside the request transaction like every other service (never commits).
Returns raw session tokens to the router, which sets them as cookies; only the
token *hash* is ever persisted.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    EMAIL_TAKEN,
    INVALID_CREDENTIALS,
    AppError,
)
from app.modules.auth.models import User, UserSession
from app.modules.auth.security import (
    hash_password,
    hash_token,
    new_session_token,
    session_expiry,
    verify_password,
)


def register(session: Session, *, email: str, password: str) -> tuple[User, str]:
    """Create a user and an initial session. Returns ``(user, raw_token)``.

    Duplicate email → 409 ``email_taken``. Registration logs the user straight
    in, so a session token comes back with the new user.
    """
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise AppError(409, EMAIL_TAKEN, "That email address is already registered.")

    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    session.flush()

    token = _create_session(session, user)
    return user, token


def login(session: Session, *, email: str, password: str) -> tuple[User, str]:
    """Verify credentials and open a session. Returns ``(user, raw_token)``.

    The 401 is **uniform**: whether the email is unknown or the password is
    wrong, the caller gets the identical ``invalid_credentials`` response, so an
    attacker cannot probe which emails are registered.
    """
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(user.password_hash, password):
        raise AppError(401, INVALID_CREDENTIALS, "Incorrect email or password.")

    token = _create_session(session, user)
    return user, token


def logout(session: Session, token: str | None) -> None:
    """Revoke a session by deleting its row. Idempotent — an unknown or missing
    token is a no-op (logout always 'succeeds')."""
    if not token:
        return
    row = session.get(UserSession, hash_token(token))
    if row is not None:
        session.delete(row)
        session.flush()


def user_for_token(session: Session, token: str | None) -> User | None:
    """Resolve a raw cookie token to its user, or None.

    Returns None for a missing, unknown, or expired token. Expired sessions are
    left for a future sweep to delete; here they simply do not authenticate.
    """
    if not token:
        return None
    row = session.get(UserSession, hash_token(token))
    if row is None:
        return None
    if row.expires_at <= datetime.now(UTC):
        return None
    return row.user


def _create_session(session: Session, user: User) -> str:
    """Mint a session token, persist only its hash, and return the raw token."""
    token = new_session_token()
    session.add(
        UserSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=session_expiry(),
        )
    )
    session.flush()
    return token
