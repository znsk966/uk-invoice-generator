"""Password hashing and session-token primitives.

Passwords: argon2id via ``argon2-cffi`` with library defaults. Tokens: a
``secrets.token_urlsafe(32)`` random string handed to the client; only its
SHA-256 hash is ever stored, so the database never holds anything replayable.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

SESSION_TTL = timedelta(days=30)

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with argon2id (library defaults)."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Return True if ``password`` matches ``password_hash``; False otherwise.

    Never raises on a mismatch — the caller turns a False into the uniform
    ``invalid_credentials`` response.
    """
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def new_session_token() -> str:
    """A fresh, URL-safe random session token. Given to the client, never stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 of a session token, hex-encoded — what we store and look up by.

    A plain hash (not a slow password hash) is right here: the token is 256 bits
    of entropy, so there is nothing to brute-force, and lookups must be fast.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    """The expiry timestamp for a session created ``now`` (default: current UTC)."""
    return (now or datetime.now(UTC)) + SESSION_TTL
