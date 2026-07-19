"""Pydantic v2 schemas for the single company profile."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyProfileBase(BaseModel):
    trading_name: str = Field(min_length=1, max_length=255)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    postcode: str = Field(min_length=1, max_length=32)
    country: str = Field(default="GB", min_length=2, max_length=2)
    vat_number: str | None = Field(default=None, max_length=32)
    company_number: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    bank_account_name: str | None = Field(default=None, max_length=255)
    bank_sort_code: str | None = Field(default=None, max_length=16)
    bank_account_number: str | None = Field(default=None, max_length=32)


class CompanyProfileUpsert(CompanyProfileBase):
    """Full set of editable fields; PUT creates or replaces the id=1 row."""


class CompanyProfileRead(CompanyProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
