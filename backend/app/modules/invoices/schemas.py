"""Pydantic v2 schemas for invoices.

Money & quantity handling (Project Law: floats never touch money):

* Every money / quantity / rate field is a ``Decimal``. Pydantic v2 parses a
  JSON number into ``Decimal`` **from the source text**, so ``10.10`` arrives
  exactly (not as the binary float ``10.0999...``). The Phase 3 frontend will
  send money as JSON *strings* anyway, which is likewise parsed exactly.
* ``allow_inf_nan=False`` on those fields rejects ``Infinity`` / ``NaN`` — values
  that are valid IEEE floats but meaningless as money.
* The server never trusts client-computed totals: request bodies carry only
  inputs (quantity, unit_price, rate code); all totals are computed server-side.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.vat import VatRateCode

# Reusable Decimal type that refuses Infinity/NaN.
Money = Annotated[Decimal, Field(allow_inf_nan=False)]


class LineInputSchema(BaseModel):
    position: int = Field(ge=1)
    description: str = Field(min_length=1)
    quantity: Money
    unit_price: Money
    vat_rate_code: VatRateCode


class _InvoiceWriteBase(BaseModel):
    client_id: int
    notes: str | None = None
    due_date: date | None = None
    lines: list[LineInputSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def _positions_unique(self) -> "_InvoiceWriteBase":
        positions = [line.position for line in self.lines]
        if len(positions) != len(set(positions)):
            raise ValueError("line positions must be unique per invoice")
        return self


class InvoiceCreate(_InvoiceWriteBase):
    pass


class InvoiceUpdate(_InvoiceWriteBase):
    """Full replace of a draft's editable fields, including lines."""


class IssueRequest(BaseModel):
    invoice_date: date | None = None
    tax_point_date: date | None = None
    due_date: date | None = None


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate_code: VatRateCode


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    number: str | None
    client_id: int
    invoice_date: date | None
    tax_point_date: date | None
    due_date: date | None
    currency: str
    notes: str | None
    lines: list[InvoiceLineRead]
    # Present for issued/void invoices; the authoritative money for those lives
    # here (written once at issue) and is never recomputed. None for drafts.
    snapshot: dict | None
    issued_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RateGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: VatRateCode
    rate: Decimal
    net: Decimal
    vat: Decimal
    gross: Decimal


class InvoiceTotalsRead(BaseModel):
    """On-demand totals for a draft (mirrors app.core.vat.InvoiceTotals)."""

    model_config = ConfigDict(from_attributes=True)

    groups: list[RateGroupRead]
    total_net: Decimal
    total_vat: Decimal
    total_gross: Decimal
