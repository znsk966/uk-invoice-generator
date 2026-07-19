"""Company profile endpoints. A single row with id=1 (enforced by CHECK)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import COMPANY_PROFILE_MISSING, AppError
from app.modules.company.models import CompanyProfile
from app.modules.company.schemas import CompanyProfileRead, CompanyProfileUpsert

router = APIRouter(prefix="/company-profile", tags=["company-profile"])

_SINGLETON_ID = 1


@router.get("", response_model=CompanyProfileRead)
def get_company_profile(session: Session = Depends(get_session)) -> CompanyProfile:
    profile = session.get(CompanyProfile, _SINGLETON_ID)
    if profile is None:
        raise AppError(
            404,
            COMPANY_PROFILE_MISSING,
            "Company profile has not been set up yet.",
        )
    return profile


@router.put("", response_model=CompanyProfileRead)
def upsert_company_profile(
    payload: CompanyProfileUpsert, session: Session = Depends(get_session)
) -> CompanyProfile:
    profile = session.get(CompanyProfile, _SINGLETON_ID)
    if profile is None:
        profile = CompanyProfile(id=_SINGLETON_ID, **payload.model_dump())
        session.add(profile)
    else:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
    session.flush()
    return profile
