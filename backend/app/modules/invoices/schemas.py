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
    """One line as the client sends it. Two shapes share this schema:

    * **Ad-hoc line** (``product_id`` null): ``description``, ``vat_rate_code``
      and ``unit_price`` are all required — the client is the source of them.
    * **Catalog line** (``product_id`` set): the server is authoritative for
      ``description`` and ``vat_rate_code`` — it copies them from the product and
      **ignores whatever the client sent**. ``unit_price`` is optional and
      defaults to the product's current price.
    """

    position: int = Field(ge=1)
    product_id: int | None = None
    description: str | None = None
    quantity: Money
    unit_price: Money | None = None
    vat_rate_code: VatRateCode | None = None

    @model_validator(mode="after")
    def _ad_hoc_lines_are_complete(self) -> "LineInputSchema":
        if self.product_id is not None:
            return self
        if self.description is None or not self.description.strip():
            raise ValueError("description is required on a line without a product")
        if self.vat_rate_code is None:
            raise ValueError("vat_rate_code is required on a line without a product")
        if self.unit_price is None:
            raise ValueError("unit_price is required on a line without a product")
        return self


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


class PreviewTotalsRequest(BaseModel):
    """Stateless totals preview for the draft editor: lines in, totals out.

    Reuses ``LineInputSchema``, so money arrives under exactly the same rules as
    a real draft — strings (or exactly-parsed JSON numbers), never floats.
    ``on_date`` selects which effective-dated rates apply; it defaults to today.
    """

    lines: list[LineInputSchema] = Field(default_factory=list)
    on_date: date | None = None


class IssueRequest(BaseModel):
    invoice_date: date | None = None
    tax_point_date: date | None = None
    due_date: date | None = None


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    product_id: int | None
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
