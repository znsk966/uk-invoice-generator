"""Auth endpoints: register, login, logout, me.

These are the only domain endpoints that do **not** require authentication
(register/login open the session; logout and me tolerate its absence). Every
other router depends on ``current_user``.
"""

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.auth import service
from app.modules.auth.deps import (
    COOKIE_NAME,
    clear_session_cookie,
    current_user,
    set_session_cookie,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(
    payload: RegisterRequest, response: Response, session: Session = Depends(get_session)
) -> User:
    """Register a new user. On success the user is logged in (cookie set)."""
    user, token = service.register(session, email=payload.email, password=payload.password)
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserRead)
def login(
    payload: LoginRequest, response: Response, session: Session = Depends(get_session)
) -> User:
    """Log in with email + password. Uniform 401 on any credential failure."""
    user, token = service.login(session, email=payload.email, password=payload.password)
    set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    session: Session = Depends(get_session),
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> Response:
    """Log out: delete the session row (real revocation) and clear the cookie.

    Idempotent — logging out without a session still returns 204.
    """
    service.logout(session, session_token)
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)) -> User:
    """The current user, or 401 ``not_authenticated``."""
    return user
