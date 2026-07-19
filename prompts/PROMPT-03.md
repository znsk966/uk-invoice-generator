# PROMPT-03 — Phase 2: API — Drafts, Issue, Snapshot, Immutability

## Precondition

The Phase 1 review fixup must be merged before starting: the `@validates` float-rejection hook on `quantity` / `unit_price` (raising `TypeError` on `float`), with its unit test. If it is not on `main` yet, do it as the first commit of this branch.

## Context

Phase 1 is merged: models, migrations, and the money core (`money.py`, `vat.py`, `numbering.py`) exist and are tested. This phase exposes the domain over HTTP and implements the money-critical **issue** transition. No frontend work — that is Phase 3.

Re-read `CLAUDE.md`. The rules that bind this phase hardest: server computes money, client displays; issued invoices are immutable with snapshots; numbers allocated only at issue inside a transaction; archive, never delete.

## Task 1 — API plumbing

- Routers under `app/modules/<name>/router.py`, wired in `create_app()` under `/api/v1`.
- Pydantic v2 schemas in `app/modules/<name>/schemas.py`. **All money and quantity fields are `Decimal`.** Document in the schema module: Pydantic v2 parses JSON numbers into `Decimal` from the source text (exact), and the Phase 3 frontend will send money as JSON strings anyway. Set `allow_inf_nan=False`.
- DB session dependency (`Depends(get_session)`) in `app/core/db.py`: yields a session, commits on success, rolls back on any exception.
- Consistent error shape for all handled errors: `{"detail": {"code": "<machine_code>", "message": "<human message>"}}`. Machine codes used below: `not_found`, `client_archived`, `invoice_not_draft`, `invoice_not_issued`, `validation_failed`, `company_profile_missing`.

## Task 2 — Clients & company profile

- `GET /api/v1/clients` (query param `include_archived=false` by default), `POST`, `GET /{id}`, `PUT /{id}`, `POST /{id}/archive`, `POST /{id}/unarchive`. **No DELETE route exists.**
- Archiving a client does not touch their invoices. Creating an invoice for an archived client → 409 `client_archived`.
- `GET /api/v1/company-profile` (404 `company_profile_missing` if the singleton row doesn't exist yet), `PUT /api/v1/company-profile` (creates or updates the id=1 row).

## Task 3 — Invoice drafts

- `POST /api/v1/invoices` — create a draft: `client_id`, optional `notes`, optional `due_date`, and `lines` (position, description, quantity, unit_price, vat_rate_code). Replaces nothing; drafts have no number, no dates fixed, no stored money.
- `GET /api/v1/invoices` (filter by `status`), `GET /{id}`.
- `PUT /api/v1/invoices/{id}` — full replace of the draft's editable fields **including lines** (delete-and-recreate lines is fine for the PoC; positions must be unique per invoice and are re-validated). Allowed only for `status = draft`; otherwise 409 `invoice_not_draft`.
- `DELETE /api/v1/invoices/{id}` — allowed **only for drafts** (this is the one legitimate delete in the system: a draft is scratch paper, not master data). Issued/void → 409 `invoice_not_draft`.
- `GET /api/v1/invoices/{id}/totals` — computes via `rates_on(session, date.today())` + `compute_totals` and returns the `InvoiceTotals` shape (groups + invoice totals). This is the endpoint the Phase 3 editor calls; it does not persist anything.

## Task 4 — Issue (the money-critical transition)

`POST /api/v1/invoices/{id}/issue` with optional body: `invoice_date` (default today), `tax_point_date` (default = invoice_date), `due_date` (optional override).

Implement as `issue_invoice(session, invoice_id, ...)` in `app/modules/invoices/service.py` — the router is a thin wrapper. Inside one transaction, in this order:

1. Load the invoice `FOR UPDATE` (`with_for_update()`); 404 if missing.
2. Validate: status is `draft` (else 409 `invoice_not_draft`); at least one line (else 422 `validation_failed`); company profile exists (else 409 `company_profile_missing`); client not archived (else 409 `client_archived`).
3. Resolve rates: `rates_on(session, tax_point_date)` — rates are taken at the **tax point**, not "today".
4. Compute totals via `compute_totals`.
5. Allocate the number: `seq = allocate_number(session, invoice_sequence_key(invoice_date.year))`, `number = format_invoice_number(invoice_date.year, seq)`.
6. Build the snapshot (Task 5), set `status=issued`, `number`, `invoice_date`, `tax_point_date`, `due_date`, `issued_at=now(tz)`.
7. Commit happens in the session dependency; any failure rolls back everything including the number (gapless).

`POST /api/v1/invoices/{id}/void` — allowed only for `issued` (else 409 `invoice_not_issued`); sets `status=void`, keeps the number and snapshot untouched (a voided number stays consumed — UK sequential-numbering practice; document this in the service docstring).

## Task 5 — Snapshot shape

`snapshot` JSONB, all money serialized as **strings** (JSON numbers are floats — banned). Shape:

```json
{
  "version": 1,
  "number": "INV-2026-00001",
  "invoice_date": "2026-07-19",
  "tax_point_date": "2026-07-19",
  "due_date": "2026-08-18",
  "currency": "GBP",
  "seller": { ...full company profile fields... },
  "client": { ...full client fields at issue time... },
  "lines": [
    { "position": 1, "description": "...", "quantity": "2.000",
      "unit_price": "10.0000", "vat_rate_code": "standard",
      "rate": "0.2000", "line_net": "20.00" }
  ],
  "groups": [ { "code": "standard", "rate": "0.2000",
                "net": "20.00", "vat": "4.00", "gross": "24.00" } ],
  "totals": { "net": "20.00", "vat": "4.00", "gross": "24.00" }
}
```

Rules: the snapshot is written once, at issue, and never updated. `GET /{id}` for an issued/void invoice serves money **from the snapshot**, never recomputed. Phase 4's PDF will read only this structure — its shape is now frozen; any future change bumps `version`.

## Task 6 — Immutability enforcement

- Service/API level: every mutating operation checks status first (the 409s above).
- Defense in depth at the DB: a trigger (raw SQL in a new Alembic migration) that raises on `UPDATE` of `invoice` rows where `OLD.status = 'issued'`, **except** the single allowed transition (`issued → void` touching only `status` and `updated_at`), and raises on any `UPDATE`/`DELETE` of `invoice_line` rows whose invoice is not a draft. Keep the trigger simple and commented — it is a tripwire, not the primary enforcement.

## Task 7 — Tests (integration tier, `tests/api/`)

Use httpx `ASGITransport` against the real app with the DB test fixtures (extend the Phase 1 conftest; same `TEST_DATABASE_URL` skip rule). Cover at minimum:

- Full lifecycle: create client → company profile → draft with lines → totals endpoint matches `compute_totals` → issue → number is `INV-{year}-00001` → GET serves snapshot money → void keeps number.
- Editing an issued invoice → 409; deleting an issued invoice → 409; issuing twice → 409.
- The DB trigger fires on a direct SQL `UPDATE` of an issued invoice's line (bypass the API deliberately in the test).
- Two drafts issued sequentially → `00001`, `00002` (gapless); a failed issue (e.g. archived client) followed by a successful one → number not burned.
- Archived client: new invoice → 409; their previously issued invoice still readable.
- Rates at tax point: issue with `tax_point_date` before `2011-01-04` → `LookupError` surfaced as 422 `validation_failed` (proves rates come from the tax point, not today).
- Float in JSON body where a string is expected still parses exactly via Pydantic — and a snapshot round-trip asserts money strings, not numbers, in the stored JSONB.

## Acceptance criteria

- [ ] Full lifecycle works through OpenAPI docs UI (`/docs`)
- [ ] OpenAPI schema generates without warnings; all money fields render as strings in examples
- [ ] All Phase 1 tests still green; new API tier green locally (with `TEST_DATABASE_URL`) and in CI
- [ ] Grep proof in PR description: no `float` in schemas/service/snapshot code; no recomputation of money for non-draft invoices; no DELETE route for clients
- [ ] Migration with the immutability trigger upgrades and downgrades cleanly

## Do NOT

- No frontend changes — Phase 3.
- No PDF — Phase 4.
- No auth, pagination, or rate limiting.
- No new dependencies without justification in the PR description.
- Do not store computed money on draft rows — totals for drafts are always computed on demand.

## Deliverable

Feature branch `phase-2-api`, PR to `main` titled "Phase 2: API — drafts, issue, snapshot, immutability", green CI, PR description with deviations and the grep proofs.
