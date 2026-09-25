"""Invoice endpoints. Thin wrappers over app.modules.invoices.service.

Every endpoint is scoped to the authenticated owner: lists show only the user's
own invoices, and a lookup of another user's invoice returns 404 ``not_found``.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import VALIDATION_FAILED, AppError
from app.core.vat import compute_totals
from app.modules.auth.deps import current_user
from app.modules.auth.models import User
from app.modules.invoices import service
from app.modules.invoices.models import Invoice, InvoiceStatus
from app.modules.invoices.schemas import (
    InvoiceCreate,
    InvoiceRead,
    InvoiceTotalsRead,
    InvoiceUpdate,
    IssueRequest,
    PreviewTotalsRequest,
)
from app.modules.vat.repository import rates_on

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    status: InvoiceStatus | None = Query(default=None),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[Invoice]:
    stmt = select(Invoice).where(Invoice.owner_id == user.id).order_by(Invoice.id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    return list(session.scalars(stmt))


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice(
    payload: InvoiceCreate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Invoice:
    return service.create_draft(session, user.id, payload)


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Invoice:
    return service.get_invoice_or_404(session, user.id, invoice_id)


@router.put("/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Invoice:
    return service.replace_draft(session, user.id, invoice_id, payload)


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Response:
    service.delete_draft(session, user.id, invoice_id)
    return Response(status_code=204)


@router.get("/{invoice_id}/totals", response_model=InvoiceTotalsRead)
def get_invoice_totals(
    invoice_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> InvoiceTotalsRead:
    """Totals for an invoice. Persists nothing.

    Behaviour depends on status, and the difference matters:

    * **draft** — computed on demand from the current lines at today's rates.
    * **issued / void** — read back from the snapshot written at issue, verbatim.
      Never recomputed: the money on an issued document is fixed, so a VAT rate
      change afterwards must not alter what this returns. This is the same
      source ``GET /invoices/{id}`` serves.
    """
    invoice = service.get_invoice_or_404(session, user.id, invoice_id)
    if invoice.status != InvoiceStatus.draft:
        return InvoiceTotalsRead.model_validate(service.totals_from_snapshot(invoice))
    totals = service.compute_invoice_totals(session, invoice, date.today())
    return InvoiceTotalsRead.model_validate(totals, from_attributes=True)


@router.post("/preview-totals", response_model=InvoiceTotalsRead)
def preview_totals(
    payload: PreviewTotalsRequest,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> InvoiceTotalsRead:
    """Compute totals for a set of lines without writing to the database.

    Stateless: nothing is created or updated. The draft editor calls this for
    live totals on **unsaved** edits, so the server stays the only thing that
    does money arithmetic without every keystroke having to autosave a draft.

    Catalog lines are resolved exactly as a save would resolve them: the
    product is loaded for the current owner (404 otherwise) and its VAT rate
    replaces whatever the client sent. Archived products are *not* rejected
    here — a stateless preview cannot tell a newly added product from one
    already on the draft, and the editor must keep showing totals for an old
    draft whose product was archived later. The save is where that rule bites.
    """
    try:
        rates = rates_on(session, payload.on_date or date.today())
    except LookupError as exc:
        raise AppError(422, VALIDATION_FAILED, str(exc)) from exc

    lines = service.resolve_lines(session, user.id, payload.lines, reject_archived=False)
    totals = compute_totals([line.to_input() for line in lines], rates)
    return InvoiceTotalsRead.model_validate(totals, from_attributes=True)


@router.post("/{invoice_id}/issue", response_model=InvoiceRead)
def issue_invoice(
    invoice_id: int,
    payload: IssueRequest | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Invoice:
    body = payload or IssueRequest()
    return service.issue_invoice(
        session,
        user.id,
        invoice_id,
        invoice_date=body.invoice_date,
        tax_point_date=body.tax_point_date,
        due_date=body.due_date,
    )


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
def void_invoice(
    invoice_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Invoice:
    return service.void_invoice(session, user.id, invoice_id)
