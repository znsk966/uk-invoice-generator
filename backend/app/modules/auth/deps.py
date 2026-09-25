"""The ``current_user`` dependency and the session-cookie contract.

Every domain router depends on ``current_user``; unauthenticated requests get a
uniform 401 ``not_authenticated``. The cookie is HTTP-only so the token is never
exposed to JavaScript.
"""

from fastapi import Cookie, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_session
from app.core.errors import NOT_AUTHENTICATED, AppError
from app.modules.auth.models import User
from app.modules.auth.service import user_for_token

COOKIE_NAME = "session"
# 30 days, matching the session TTL in security.py.
_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def set_session_cookie(response: Response, token: str) -> None:
    """Write the session cookie: HTTP-only, SameSite=Lax, Secure outside dev."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie (logout). Matches the attributes it was set with."""
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def current_user(
    session: Session = Depends(get_session),
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> User:
    """Resolve the authenticated user from the session cookie, or raise 401.

    Reads the cookie, hashes it, looks up an unexpired session, loads the user.
    Anything missing — no cookie, unknown token, expired session — is the same
    ``not_authenticated`` 401, leaking nothing about which case it was.
    """
    user = user_for_token(session, session_token)
    if user is None:
        raise AppError(401, NOT_AUTHENTICATED, "Not authenticated.")
    return user
