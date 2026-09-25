"""Company profile endpoints. One profile per user (UNIQUE owner_id).

Scoped to the authenticated owner throughout: a user only ever sees, creates, or
edits their own profile. A user without a profile yet gets 404
``company_profile_missing`` — the same code the frontend keys off to prompt setup.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import COMPANY_PROFILE_MISSING, AppError
from app.modules.auth.deps import current_user
from app.modules.auth.models import User
from app.modules.company.models import CompanyProfile
from app.modules.company.schemas import CompanyProfileRead, CompanyProfileUpsert

router = APIRouter(prefix="/company-profile", tags=["company-profile"])


def _get_for_owner(session: Session, owner_id: int) -> CompanyProfile | None:
    return session.scalar(select(CompanyProfile).where(CompanyProfile.owner_id == owner_id))


@router.get("", response_model=CompanyProfileRead)
def get_company_profile(
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CompanyProfile:
    profile = _get_for_owner(session, user.id)
    if profile is None:
        raise AppError(
            404,
            COMPANY_PROFILE_MISSING,
            "Company profile has not been set up yet.",
        )
    return profile


@router.put("", response_model=CompanyProfileRead)
def upsert_company_profile(
    payload: CompanyProfileUpsert,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> CompanyProfile:
    profile = _get_for_owner(session, user.id)
    if profile is None:
        profile = CompanyProfile(owner_id=user.id, **payload.model_dump())
        session.add(profile)
    else:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
    session.flush()
    return profile
