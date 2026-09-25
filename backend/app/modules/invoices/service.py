"""Invoice service layer: draft CRUD, totals, and the money-critical issue/void
transitions. Routers are thin wrappers over these functions.

Every function runs inside the request's transaction (opened by ``get_session``),
which commits on success and rolls back on any error. That is what makes issue
atomic: if anything fails after a number is allocated, the rollback returns the
number to the sequence, keeping invoice numbering gapless.
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    CLIENT_ARCHIVED,
    COMPANY_PROFILE_MISSING,
    INVOICE_NOT_DRAFT,
    INVOICE_NOT_ISSUED,
    NOT_FOUND,
    PRODUCT_ARCHIVED,
    VALIDATION_FAILED,
    AppError,
)
from app.core.money import round_money
from app.core.numbering import (
    allocate_number,
    format_invoice_number,
    invoice_sequence_key,
)
from app.core.vat import InvoiceTotals, LineInput, VatRateCode, compute_totals
from app.modules.clients.models import Client
from app.modules.company.models import CompanyProfile
from app.modules.invoices.models import Invoice, InvoiceLine, InvoiceStatus
from app.modules.products.models import Product
from app.modules.products.service import get_product_or_404
from app.modules.vat.repository import rates_on

# v2 (Phase 5) adds product_id / product_code / kind to each line, null for
# ad-hoc lines. v1 snapshots already stored stay valid: readers must treat the
# v2 line fields as optional. Snapshots are never backfilled or rewritten.
SNAPSHOT_VERSION = 2

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


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
def get_invoice_or_404(
    session: Session, owner_id: int, invoice_id: int, *, for_update: bool = False
) -> Invoice:
    """Load one of ``owner_id``'s invoices or raise 404.

    Scoped to the owner: another user's invoice returns 404 ``not_found``, never
    403 — existence must not leak across owners.

    ``for_update=True`` takes a row lock (``SELECT ... FOR UPDATE``) for the rest
    of the request's transaction. The state transitions use it so two concurrent
    issues (or voids) of the same invoice serialise: the second waits, then sees
    the status the first left behind and is rejected.
    """
    stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == owner_id)
    if for_update:
        stmt = stmt.with_for_update()
    invoice = session.execute(stmt).scalar_one_or_none()
    if invoice is None:
        raise AppError(404, NOT_FOUND, f"Invoice {invoice_id} not found.")
    return invoice


def _require_client(session: Session, owner_id: int, client_id: int) -> Client:
    """Load one of ``owner_id``'s clients or raise 404. Archived clients pass —
    issued invoices must stay readable after their client is archived."""
    client = session.scalar(
        select(Client).where(Client.id == client_id, Client.owner_id == owner_id)
    )
    if client is None:
        raise AppError(404, NOT_FOUND, f"Client {client_id} not found.")
    return client


def _require_active_client(session: Session, owner_id: int, client_id: int) -> Client:
    """Like _require_client, but also rejects archived clients (409). Used when
    attaching a client to a draft — you cannot invoice an archived client."""
    client = _require_client(session, owner_id, client_id)
    if client.archived_at is not None:
        raise AppError(409, CLIENT_ARCHIVED, "Cannot use an archived client on an invoice.")
    return client


# --------------------------------------------------------------------------- #
# Line resolution (catalog links)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ResolvedLine:
    """A request line with every field settled: what gets stored or totalled."""

    position: int
    product_id: int | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate_code: VatRateCode

    def to_model(self) -> InvoiceLine:
        return InvoiceLine(
            position=self.position,
            product_id=self.product_id,
            description=self.description,
            quantity=self.quantity,
            unit_price=self.unit_price,
            vat_rate_code=self.vat_rate_code,
        )

    def to_input(self) -> LineInput:
        return LineInput(
            quantity=self.quantity,
            unit_price=self.unit_price,
            vat_rate_code=self.vat_rate_code,
        )


def resolve_lines(
    session: Session,
    owner_id: int,
    lines: Iterable,
    *,
    previously_linked: Collection[int] = (),
    reject_archived: bool = True,
) -> list[ResolvedLine]:
    """Settle each request line, applying the catalog rules.

    Ad-hoc lines (no ``product_id``) pass through as sent. For a catalog line:

    * the product is loaded **for this owner** — anyone else's is 404;
    * ``description`` and ``vat_rate_code`` are copied from the product, and
      whatever the client sent for them is ignored: the server is authoritative
      (the DB trigger would reject a mismatch anyway);
    * ``unit_price`` is the client's, or the product's current price if omitted;
    * an archived product is 409 ``product_archived`` — but only if it is being
      *newly* linked. A product already in ``previously_linked`` (i.e. on the
      draft before this save) may stay even though it was archived since, so
      re-saving an old draft never fails. ``reject_archived=False`` skips the
      check entirely (the stateless preview, which cannot tell new from old).
    """
    products: dict[int, Product] = {}
    resolved = []
    for line in lines:
        if line.product_id is None:
            resolved.append(
                ResolvedLine(
                    position=line.position,
                    product_id=None,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    vat_rate_code=line.vat_rate_code,
                )
            )
            continue

        product = products.get(line.product_id)
        if product is None:
            product = get_product_or_404(session, owner_id, line.product_id)
            products[line.product_id] = product
        if (
            reject_archived
            and product.archived_at is not None
            and product.id not in previously_linked
        ):
            raise AppError(
                409,
                PRODUCT_ARCHIVED,
                f"Product {product.code!r} is archived and cannot be added to an invoice.",
            )
        resolved.append(
            ResolvedLine(
                position=line.position,
                product_id=product.id,
                description=product.description,
                quantity=line.quantity,
                unit_price=line.unit_price if line.unit_price is not None else product.unit_price,
                vat_rate_code=product.vat_rate_code,
            )
        )
    return resolved


# --------------------------------------------------------------------------- #
# Draft CRUD
# --------------------------------------------------------------------------- #
def create_draft(session: Session, owner_id: int, payload) -> Invoice:
    """Create a draft invoice for ``owner_id``. Drafts have no number, no fixed
    dates, no stored money — only the inputs."""
    _require_active_client(session, owner_id, payload.client_id)
    lines = resolve_lines(session, owner_id, payload.lines)
    invoice = Invoice(
        owner_id=owner_id,
        status=InvoiceStatus.draft,
        client_id=payload.client_id,
        notes=payload.notes,
        due_date=payload.due_date,
    )
    invoice.lines = [line.to_model() for line in lines]
    session.add(invoice)
    session.flush()
    return invoice


def replace_draft(session: Session, owner_id: int, invoice_id: int, payload) -> Invoice:
    """Full replace of a draft's editable fields, including its lines.

    Only ``draft`` invoices are editable; anything else is immutable master data
    and returns 409. Lines are replaced wholesale (delete-and-recreate) — fine
    for the PoC; the position-uniqueness invariant is re-validated.
    """
    invoice = get_invoice_or_404(session, owner_id, invoice_id)
    if invoice.status != InvoiceStatus.draft:
        raise AppError(409, INVOICE_NOT_DRAFT, "Only draft invoices can be edited.")
    _require_active_client(session, owner_id, payload.client_id)
    # Products already on the draft may stay even if archived since; read them
    # before the lines are replaced.
    previously_linked = {line.product_id for line in invoice.lines if line.product_id}
    lines = resolve_lines(session, owner_id, payload.lines, previously_linked=previously_linked)

    invoice.client_id = payload.client_id
    invoice.notes = payload.notes
    invoice.due_date = payload.due_date
    # delete-orphan cascade removes the old lines when the collection is replaced.
    invoice.lines = [line.to_model() for line in lines]
    session.flush()
    return invoice


def delete_draft(session: Session, owner_id: int, invoice_id: int) -> None:
    """Delete a draft. This is the one legitimate delete in the system: a draft
    is scratch paper, not master data. Issued/void invoices are never deleted."""
    invoice = get_invoice_or_404(session, owner_id, invoice_id)
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
    and is read back with ``totals_from_snapshot`` instead — its money was
    written into the snapshot at issue and is served from it verbatim, never
    recomputed.

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
    """Render a date as an ISO-8601 string for the snapshot, preserving None."""
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
    (JSON numbers are floats — banned). Shape is versioned; the PDF (Phase 6)
    reads only this structure and must accept both v1 and v2 lines."""
    lines = []
    for line in invoice.lines:
        rate = rates[line.vat_rate_code]
        line_net = round_money(line.quantity * line.unit_price)
        product = line.product
        lines.append(
            {
                "position": line.position,
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "vat_rate_code": line.vat_rate_code.value,
                "rate": str(rate),
                "line_net": str(line_net),
                # v2: catalog provenance, null on ad-hoc lines.
                "product_id": product.id if product is not None else None,
                "product_code": product.code if product is not None else None,
                "kind": product.kind.value if product is not None else None,
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
    owner_id: int,
    invoice_id: int,
    *,
    invoice_date: date | None = None,
    tax_point_date: date | None = None,
    due_date: date | None = None,
) -> Invoice:
    """Issue one of ``owner_id``'s draft invoices. Runs inside the request
    transaction, in this order:

    load FOR UPDATE -> validate -> resolve rates at the tax point -> compute
    totals -> allocate the gapless number (from the owner's sequence) -> write
    the snapshot and freeze the header. If any step fails, the caller's
    transaction rolls back and the allocated number is returned to the sequence
    (never burned).
    """
    invoice = get_invoice_or_404(session, owner_id, invoice_id, for_update=True)

    if invoice.status != InvoiceStatus.draft:
        raise AppError(409, INVOICE_NOT_DRAFT, "Only draft invoices can be issued.")
    if not invoice.lines:
        raise AppError(422, VALIDATION_FAILED, "Cannot issue an invoice with no lines.")

    seller = session.scalar(select(CompanyProfile).where(CompanyProfile.owner_id == owner_id))
    if seller is None:
        raise AppError(409, COMPANY_PROFILE_MISSING, "Set up the company profile before issuing.")

    client = _require_client(session, owner_id, invoice.client_id)
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

    seq = allocate_number(session, owner_id, invoice_sequence_key(resolved_invoice_date.year))
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


def void_invoice(session: Session, owner_id: int, invoice_id: int) -> Invoice:
    """Void one of ``owner_id``'s issued invoices.

    Only ``issued`` invoices can be voided. The number and snapshot are left
    untouched: under UK sequential-numbering practice a voided number stays
    consumed (the sequence must have no gaps), so we never reclaim or blank it.
    """
    invoice = get_invoice_or_404(session, owner_id, invoice_id, for_update=True)
    if invoice.status != InvoiceStatus.issued:
        raise AppError(409, INVOICE_NOT_ISSUED, "Only issued invoices can be voided.")
    invoice.status = InvoiceStatus.void
    session.flush()
    return invoice
