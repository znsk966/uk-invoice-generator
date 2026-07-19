"""Pydantic v2 schemas for clients.

Clients carry no money fields, so there is nothing Decimal here; the money
conventions live in the invoices schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    postcode: str = Field(min_length=1, max_length=32)
    country: str = Field(default="GB", min_length=2, max_length=2)
    vat_number: str | None = Field(default=None, max_length=32)
    # Plain str (not EmailStr) to avoid pulling in the email-validator dependency;
    # the PoC does not need strict RFC email validation.
    email: str | None = Field(default=None, max_length=255)


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    """Full replace of the editable fields (PUT semantics)."""


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
