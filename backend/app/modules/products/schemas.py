"""Pydantic v2 schemas for the product catalog.

Money follows the invoice conventions: ``Decimal`` parsed exactly from the
source text, ``allow_inf_nan=False``, serialised back as a JSON string.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.vat import VatRateCode
from app.modules.products.models import ProductKind

# A catalog price: exact Decimal, never Infinity/NaN, never negative.
Price = Annotated[Decimal, Field(allow_inf_nan=False, ge=0)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Fields that form a product's identity. A PATCH naming any of them is a 409
# ``product_immutable`` (not a 422): the request is well-formed, it asks for a
# change the catalog rule forbids.
IMMUTABLE_FIELDS = frozenset({"code", "description", "kind", "vat_rate_code"})


class ProductCreate(BaseModel):
    code: NonBlank = Field(max_length=64)
    description: NonBlank
    kind: ProductKind
    vat_rate_code: VatRateCode
    unit_price: Price


class ProductPriceUpdate(BaseModel):
    """The only edit a product accepts. Anything else is rejected — see the
    PATCH route for how extra fields map to 409 vs 422."""

    model_config = ConfigDict(extra="forbid")

    unit_price: Price


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: str
    kind: ProductKind
    vat_rate_code: VatRateCode
    unit_price: Decimal
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
