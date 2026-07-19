"""Invoice endpoints. Thin wrappers over app.modules.invoices.service."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.invoices import service
from app.modules.invoices.models import Invoice, InvoiceStatus
from app.modules.invoices.schemas import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceTotalsRead,
    InvoiceUpdate,
    IssueRequest,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    status: InvoiceStatus | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    return list(session.scalars(stmt))


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice(payload: InvoiceCreate, session: Session = Depends(get_session)) -> Invoice:
    return service.create_draft(session, payload)


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, session: Session = Depends(get_session)) -> Invoice:
    return service.get_invoice_or_404(session, invoice_id)


@router.put("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int, payload: InvoiceUpdate, session: Session = Depends(get_session)
) -> Invoice:
    return service.replace_draft(session, invoice_id, payload)


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: int, session: Session = Depends(get_session)) -> Response:
    service.delete_draft(session, invoice_id)
    return Response(status_code=204)


@router.get("/{invoice_id}/totals", response_model=InvoiceTotalsRead)
def get_invoice_totals(
    invoice_id: int, session: Session = Depends(get_session)
) -> InvoiceTotalsRead:
    """Compute a draft's totals on demand (rates as of today). Persists nothing."""
    invoice = service.get_invoice_or_404(session, invoice_id)
    totals = service.compute_invoice_totals(session, invoice, date.today())
    return InvoiceTotalsRead.model_validate(totals, from_attributes=True)


@router.post("/{invoice_id}/issue", response_model=InvoiceRead)
def issue_invoice(
    invoice_id: int,
    payload: IssueRequest | None = None,
    session: Session = Depends(get_session),
) -> Invoice:
    body = payload or IssueRequest()
    return service.issue_invoice(
        session,
        invoice_id,
        invoice_date=body.invoice_date,
        tax_point_date=body.tax_point_date,
        due_date=body.due_date,
    )


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
def void_invoice(invoice_id: int, session: Session = Depends(get_session)) -> Invoice:
    return service.void_invoice(session, invoice_id)
