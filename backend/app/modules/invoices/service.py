"""Invoice service layer: draft CRUD, totals, and the money-critical issue/void
transitions. Routers are thin wrappers over these functions.

Every function runs inside the request's transaction (opened by ``get_session``),
which commits on success and rolls back on any error. That is what makes issue
atomic: if anything fails after a number is allocated, the rollback returns the
number to the sequence, keeping invoice numbering gapless.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    CLIENT_ARCHIVED,
    COMPANY_PROFILE_MISSING,
    INVOICE_NOT_DRAFT,
    INVOICE_NOT_ISSUED,
    NOT_FOUND,
    VALIDATION_FAILED,
    AppError,
)
from app.core.money import round_money
from app.core.numbering import (
    allocate_number,
    format_invoice_number,
    invoice_sequence_key,
)
from app.core.vat import InvoiceTotals, LineInput, compute_totals
from app.modules.clients.models import Client
from app.modules.company.models import CompanyProfile
from app.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from app.modules.vat.repository import rates_on

SNAPSHOT_VERSION = 1

_SELLER_FIELDS = (
    "trading_name",
    "address_line1",
    "address_line2",
    "city",
    "postcode",
    "country",
    "vat_number",
    "company_number",
    "email",
    "phone",
    "bank_account_name",
    "bank_sort_code",
    "bank_account_number",
)
_CLIENT_FIELDS = (
    "name",
    "address_line1",
    "address_line2",
    "city",
    "postcode",
    "country",
    "vat_number",
    "email",
)

_COMPANY_SINGLETON_ID = 1


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
def get_invoice_or_404(session: Session, invoice_id: int, *, for_update: bool = False) -> Invoice:
    if for_update:
        invoice = session.execute(
            select(Invoice).where(Invoice.id == invoice_id).with_for_update()
        ).scalar_one_or_none()
    else:
        invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise AppError(404, NOT_FOUND, f"Invoice {invoice_id} not found.")
    return invoice


def _require_client(session: Session, client_id: int) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise AppError(404, NOT_FOUND, f"Client {client_id} not found.")
    return client


def _require_active_client(session: Session, client_id: int) -> Client:
    """Like _require_client, but also rejects archived clients (409). Used when
    attaching a client to a draft — you cannot invoice an archived client."""
    client = _require_client(session, client_id)
    if client.archived_at is not None:
        raise AppError(409, CLIENT_ARCHIVED, "Cannot use an archived client on an invoice.")
    return client


# --------------------------------------------------------------------------- #
# Draft CRUD
# --------------------------------------------------------------------------- #
def create_draft(session: Session, payload) -> Invoice:
    """Create a draft invoice. Drafts have no number, no fixed dates, no stored
    money — only the inputs."""
    _require_active_client(session, payload.client_id)
    invoice = Invoice(
        status=InvoiceStatus.draft,
        client_id=payload.client_id,
        notes=payload.notes,
        due_date=payload.due_date,
    )
    invoice.lines = [
        InvoiceLine(
            position=line.position,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            vat_rate_code=line.vat_rate_code,
        )
        for line in payload.lines
    ]
    session.add(invoice)
    session.flush()
    return invoice


def replace_draft(session: Session, invoice_id: int, payload) -> Invoice:
    """Full replace of a draft's editable fields, including its lines.

    Only ``draft`` invoices are editable; anything else is immutable master data
    and returns 409. Lines are replaced wholesale (delete-and-recreate) — fine
    for the PoC; the position-uniqueness invariant is re-validated.
    """
    invoice = get_invoice_or_404(session, invoice_id)
    if invoice.status != InvoiceStatus.draft:
        raise AppError(409, INVOICE_NOT_DRAFT, "Only draft invoices can be edited.")
    _require_active_client(session, payload.client_id)

    invoice.client_id = payload.client_id
    invoice.notes = payload.notes
    invoice.due_date = payload.due_date
    # delete-orphan cascade removes the old lines when the collection is replaced.
    invoice.lines = [
        InvoiceLine(
            position=line.position,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            vat_rate_code=line.vat_rate_code,
        )
        for line in payload.lines
    ]
    session.flush()
    return invoice


def delete_draft(session: Session, invoice_id: int) -> None:
    """Delete a draft. This is the one legitimate delete in the system: a draft
    is scratch paper, not master data. Issued/void invoices are never deleted."""
    invoice = get_invoice_or_404(session, invoice_id)
    if invoice.status != InvoiceStatus.draft:
        raise AppError(409, INVOICE_NOT_DRAFT, "Only draft invoices can be deleted.")
    session.delete(invoice)
    session.flush()


# --------------------------------------------------------------------------- #
# Totals (drafts, on demand — never persisted)
# --------------------------------------------------------------------------- #
def totals_from_snapshot(invoice: Invoice) -> dict:
    """Read an issued/void invoice's totals back out of its snapshot.

    No arithmetic happens here: the money strings written at issue are handed
    back verbatim, in the same shape ``compute_invoice_totals`` produces. This is
    the source of truth ``GET /invoices/{id}`` already serves, so the two
    endpoints cannot disagree — which they would if this recomputed, since a VAT
    rate change after issue would produce different numbers from the ones on the
    issued document.
    """
    snapshot = invoice.snapshot or {}
    totals = snapshot.get("totals", {})
    return {
        "groups": snapshot.get("groups", []),
        "total_net": totals.get("net"),
        "total_vat": totals.get("vat"),
        "total_gross": totals.get("gross"),
    }


def compute_invoice_totals(session: Session, invoice: Invoice, on_date: date) -> InvoiceTotals:
    """Compute an invoice's totals from its current lines, at ``on_date``'s rates.

    Persists nothing — this is the on-demand view a draft's editor asks for.
    Only drafts should reach this: an issued invoice's money is fixed at issue
    and is read back with ``totals_from_snapshot`` instead.

    Propagates :class:`LookupError` from ``rates_on`` when a rate is missing for
    the date; callers decide how to surface it.
    """
    rates = rates_on(session, on_date)
    lines = [
        LineInput(
            quantity=line.quantity,
            unit_price=line.unit_price,
            vat_rate_code=line.vat_rate_code,
        )
        for line in invoice.lines
    ]
    return compute_totals(lines, rates)


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #
def _date_str(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def build_snapshot(
    *,
    invoice: Invoice,
    seller: CompanyProfile,
    client: Client,
    totals: InvoiceTotals,
    rates,
    number: str,
    invoice_date: date,
    tax_point_date: date,
    due_date: date | None,
) -> dict:
    """Freeze everything an issued invoice needs, with all money as strings
    (JSON numbers are floats — banned). Shape is versioned and frozen; Phase 4's
    PDF reads only this structure."""
    lines = []
    for line in invoice.lines:
        rate = rates[line.vat_rate_code]
        line_net = round_money(line.quantity * line.unit_price)
        lines.append(
            {
                "position": line.position,
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "vat_rate_code": line.vat_rate_code.value,
                "rate": str(rate),
                "line_net": str(line_net),
            }
        )

    groups = [
        {
            "code": group.code.value,
            "rate": str(group.rate),
            "net": str(group.net),
            "vat": str(group.vat),
            "gross": str(group.gross),
        }
        for group in totals.groups
    ]

    return {
        "version": SNAPSHOT_VERSION,
        "number": number,
        "invoice_date": _date_str(invoice_date),
        "tax_point_date": _date_str(tax_point_date),
        "due_date": _date_str(due_date),
        "currency": invoice.currency,
        "seller": {field: getattr(seller, field) for field in _SELLER_FIELDS},
        "client": {field: getattr(client, field) for field in _CLIENT_FIELDS},
        "lines": lines,
        "groups": groups,
        "totals": {
            "net": str(totals.total_net),
            "vat": str(totals.total_vat),
            "gross": str(totals.total_gross),
        },
    }


# --------------------------------------------------------------------------- #
# Issue / void
# --------------------------------------------------------------------------- #
def issue_invoice(
    session: Session,
    invoice_id: int,
    *,
    invoice_date: date | None = None,
    tax_point_date: date | None = None,
    due_date: date | None = None,
) -> Invoice:
    """Issue a draft invoice. Runs inside the request transaction, in this order:

    load FOR UPDATE -> validate -> resolve rates at the tax point -> compute
    totals -> allocate the gapless number -> write the snapshot and freeze the
    header. If any step fails, the caller's transaction rolls back and the
    allocated number is returned to the sequence (never burned).
    """
    invoice = get_invoice_or_404(session, invoice_id, for_update=True)

    if invoice.status != InvoiceStatus.draft:
        raise AppError(409, INVOICE_NOT_DRAFT, "Only draft invoices can be issued.")
    if not invoice.lines:
        raise AppError(422, VALIDATION_FAILED, "Cannot issue an invoice with no lines.")

    seller = session.get(CompanyProfile, _COMPANY_SINGLETON_ID)
    if seller is None:
        raise AppError(409, COMPANY_PROFILE_MISSING, "Set up the company profile before issuing.")

    client = _require_client(session, invoice.client_id)
    if client.archived_at is not None:
        raise AppError(409, CLIENT_ARCHIVED, "Cannot issue an invoice for an archived client.")

    resolved_invoice_date = invoice_date or date.today()
    resolved_tax_point = tax_point_date or resolved_invoice_date

    # Rates are taken at the tax point, not "today". A tax point with no
    # applicable rate (e.g. before the seed date) surfaces as 422.
    try:
        rates = rates_on(session, resolved_tax_point)
    except LookupError as exc:
        raise AppError(422, VALIDATION_FAILED, str(exc)) from exc

    lines = [
        LineInput(
            quantity=line.quantity,
            unit_price=line.unit_price,
            vat_rate_code=line.vat_rate_code,
        )
        for line in invoice.lines
    ]
    totals = compute_totals(lines, rates)

    seq = allocate_number(session, invoice_sequence_key(resolved_invoice_date.year))
    number = format_invoice_number(resolved_invoice_date.year, seq)

    invoice.snapshot = build_snapshot(
        invoice=invoice,
        seller=seller,
        client=client,
        totals=totals,
        rates=rates,
        number=number,
        invoice_date=resolved_invoice_date,
        tax_point_date=resolved_tax_point,
        due_date=due_date if due_date is not None else invoice.due_date,
    )
    invoice.status = InvoiceStatus.issued
    invoice.number = number
    invoice.invoice_date = resolved_invoice_date
    invoice.tax_point_date = resolved_tax_point
    if due_date is not None:
        invoice.due_date = due_date
    invoice.issued_at = datetime.now(UTC)
    session.flush()
    return invoice


def void_invoice(session: Session, invoice_id: int) -> Invoice:
    """Void an issued invoice.

    Only ``issued`` invoices can be voided. The number and snapshot are left
    untouched: under UK sequential-numbering practice a voided number stays
    consumed (the sequence must have no gaps), so we never reclaim or blank it.
    """
    invoice = get_invoice_or_404(session, invoice_id, for_update=True)
    if invoice.status != InvoiceStatus.issued:
        raise AppError(409, INVOICE_NOT_ISSUED, "Only issued invoices can be voided.")
    invoice.status = InvoiceStatus.void
    session.flush()
    return invoice
