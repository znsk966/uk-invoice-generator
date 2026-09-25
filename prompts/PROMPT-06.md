# PROMPT-06 — Phase 5: Product & Service Catalog

## Context

Phase 4 (auth & per-user ownership, PR #8) is merged. This phase adds a per-user catalog of products and services, and links invoice lines to it. Re-read `CLAUDE.md` first. Rule 9 (ownership) governs the new table from birth, and rules 3 and 5 (immutability, archive-not-delete) now apply to catalog entries too.

**The catalog rule for this phase, to be written into the law in Task 6:** a product's identity is immutable. Once created, its `code`, `description`, `kind` and `vat_rate_code` can never change. To change any of them, archive the product and create a new one. Only `unit_price` (the default price for new lines) is editable. Because identity is immutable, a line linked to a product can safely carry the product's description and VAT rate: they can never drift apart.

## Task 0 — Fixes carried over from the Phase 4 review

1. **Concurrent registration returns 500.** Four simultaneous `POST /auth/register` calls with the same email returned `[201, 500, 500, 500]`. The DB constraint held, but the losers got an unhandled `UniqueViolation`. In `auth/service.register`, catch `IntegrityError` on the flush that inserts the user. Roll back to a savepoint (`session.begin_nested()`) so the request transaction stays usable, then raise 409 `email_taken`. Keep the pre-check as the fast path. Test: 4 threads, one email, expect exactly `[201, 409, 409, 409]`.
2. **Login timing side-channel.** An unknown email answers in about 5 ms, a registered one in about 120 ms, because argon2 verification is skipped when the user is missing. When the user doesn't exist, verify the submitted password against a module-level dummy hash (computed once at import with `hash_password`) and discard the result. Add a comment explaining why, and note that `/register`'s 409 already reveals registration, so this is defense in depth. Test: assert that the verify function is called in the unknown-email path (mock or spy). Do not write a wall-clock timing test; it would be flaky in CI.

## Task 1 — Product model & migration

Module `app/modules/products/`. Table `product`:

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `owner_id` | FK `user.id`, NOT NULL, `ON DELETE RESTRICT`, indexed | rule 9 |
| `code` | text NOT NULL | SKU/short code; `UNIQUE (owner_id, code)`; **immutable** |
| `description` | text NOT NULL | what appears on the invoice line; **immutable** |
| `kind` | enum `goods` / `service` NOT NULL | **immutable** (UK tax-point rules differ for goods and services, so record it now) |
| `vat_rate_code` | existing `vat_rate_code` enum NOT NULL | **immutable** |
| `unit_price` | `Numeric(12,4)` NOT NULL, `CHECK (unit_price >= 0)` | the only mutable field; default price for new lines |
| `archived_at` | timestamptz nullable | archive, never delete |
| `created_at` / `updated_at` | via `TimestampMixin` | |

- A `@validates("unit_price")` hook using `reject_float`, the same as invoice lines.
- `invoice_line` gains a `product_id` column: FK `product.id`, nullable, `ON DELETE RESTRICT`, indexed. **Ad-hoc lines (`product_id` NULL) remain allowed.** An invoice can mix catalog lines and one-off lines.
- The migration is additive, so no empty-DB guard is needed. It must round-trip upgrade and downgrade cleanly.

## Task 2 — Database enforcement (triggers, same pattern as `immutability.py`)

Put the DDL in `app/modules/products/integrity.py`, shared between the migration and the test harness exactly as the invoice triggers are.

1. **`product` BEFORE UPDATE:** raise if `code`, `description`, `kind`, `vat_rate_code` or `owner_id` changes (`IS DISTINCT FROM`). `unit_price`, `archived_at` and `updated_at` may change.
2. **`product` BEFORE DELETE:** always raise. Products are archived, never deleted. The FK `RESTRICT` already blocks deleting referenced products; this trigger also covers unreferenced ones.
3. **`invoice_line` BEFORE INSERT OR UPDATE, when `NEW.product_id IS NOT NULL`:** raise unless all three hold:
   - the product's `owner_id` equals the parent invoice's `owner_id` (no cross-owner product links, even via raw SQL);
   - `NEW.description = product.description`;
   - `NEW.vat_rate_code = product.vat_rate_code`.

   The line keeps its own `description` and `vat_rate_code` columns (NOT NULL, unchanged). For linked lines they are enforced copies of immutable product fields. This keeps `vat.py`, the totals paths and the editor unchanged while giving a DB-level guarantee of consistency.
   - The existing line-immutability trigger still fires, so linked lines on issued invoices are frozen as before. Check that both triggers coexist, and document their firing order in a comment.

## Task 3 — API

`/api/v1/products`. Every endpoint depends on `current_user` and is owner-scoped; another user's product returns 404 `not_found`.

- `GET` (`include_archived=false` default; optional `kind` filter), `POST`, `GET /{id}`.
- `PATCH /{id}`: accepts **only** `unit_price`. A body containing any other field returns 409 `product_immutable`, with a message naming the field and saying "archive this product and create a new one". Use an explicit schema that forbids extra fields (`extra="forbid"`), and map the validation error to that code.
- `POST /{id}/archive`, `POST /{id}/unarchive`. No DELETE route.
- A duplicate `code` for the same owner returns 409 `product_code_taken`. Catch `IntegrityError` (savepoint pattern, as in Task 0.1) so concurrent creates never 500.

**Invoice lines** (`POST /invoices`, `PUT /invoices/{id}`, `POST /invoices/preview-totals`):
- The line schema gains an optional `product_id`.
- If `product_id` is set: load the product **for the current owner** (else 404 `not_found`). An archived product returns 409 `product_archived`, but only when the product is *newly* added to the line: re-saving a draft whose existing line links a product that was archived later is allowed. Then set the line's `description` and `vat_rate_code` from the product and **ignore any description/VAT the client sent**. Document that the server is authoritative for these. `unit_price` comes from the request (the frontend pre-fills it from the product); if omitted, default to the product's current `unit_price`.
- If `product_id` is null: behaves exactly as before (free-text description, chosen VAT).
- Product price changes never touch existing lines. Lines store their own `unit_price`, and the snapshot freezes everything at issue.

**Snapshot version 2.** Each line gains `product_id`, `product_code` and `kind`, all null for ad-hoc lines. Bump `SNAPSHOT_VERSION` to 2. v1 snapshots already stored stay valid and readable. No backfill: every reader must treat the new fields as optional.

## Task 4 — Frontend

- **`/products` page** (new sidebar entry between Clients and Settings): a table with code, description, kind, VAT rate and price, via `formatMoney` from server strings. Also a "Show archived" toggle, and Archive/Unarchive actions with confirmation.
- **New product form:** all fields editable.
- **Edit product:** only price is editable. Code, description, kind and VAT are shown read-only with a one-line note: "Description and VAT rate can't be changed after creation. Archive this product and create a new one." Nothing in the UI suggests otherwise.
- **Invoice editor:** each line gets a product picker (active products, searchable by code or description) with a "Custom line" option.
  - Picking a product fills description and VAT from the product and **locks both fields** (read-only, visually distinct), and pre-fills price (editable).
  - Switching back to "Custom line" unlocks description and VAT.
  - An existing line linked to an archived product shows it with an "archived" badge and stays valid.
- **Read-only invoice view:** show `product_code` next to the description when present. Must render v1 snapshots (no product fields) without errors.
- String money only, as before. The grep proofs from Phase 3 still apply.

## Task 5 — Tests

**Backend:**
- **Product CRUD and scoping:** B cannot see, patch, archive or link A's products (404 on each).
- **Immutability through the API:** `PATCH` with `description`, `vat_rate_code`, `code` or `kind` each returns 409 `product_immutable`; a price-only `PATCH` returns 200.
- **Immutability through raw SQL (bypassing the API):**
  - `UPDATE product SET description = …` raises;
  - `UPDATE product SET vat_rate_code = …` raises;
  - `DELETE FROM product` raises;
  - `UPDATE product SET unit_price = …` succeeds.
- **Line integrity through raw SQL:**
  - inserting a line linked to a product with a mismatched description raises;
  - a mismatched VAT code raises;
  - a product owned by another user raises.
- **Server authority:** a line posted with `product_id` plus a different description or VAT is stored with the product's values.
- **Archived product:** adding it to a new line returns 409 `product_archived`; re-saving a draft that already links it returns 200.
- **Price independence:** create a draft line from a product, `PATCH` the product price, and confirm the draft line's price is unchanged; `preview-totals` and issue use the line price.
- **Snapshot v2:** an issued invoice with one catalog line and one ad-hoc line has `version: 2`, product fields on the catalog line, and nulls on the ad-hoc line.
- **Concurrency:** two concurrent creates with the same product code return `[201, 409]`, never 500.
- **Task 0 tests** (above).

**Frontend (msw):**
- Picking a product locks description and VAT and pre-fills price.
- Switching to "Custom line" unlocks them.
- The edit-product form exposes only price.
- The read-only view renders a v1 snapshot and a v2 snapshot.

## Task 6 — Docs & law

- **CLAUDE.md:** amend rule 5 (master data). Products join clients under archive-not-delete, and a product's identity (code, description, kind, VAT rate) is immutable; changes mean archive and create new.
- **docs/INVOICING.md:** add a catalog section, the linked-line integrity trigger, and the snapshot v2 reference (fields added, v1 compatibility).
- **docs/ARCHITECTURE.md:** add the products module to the module map.
- **docs/PHASE-PLAN.md:** mark Phase 4 done (PR #8) and this phase as Phase 5; PDF becomes Phase 6.
- **README:** add the catalog to the feature list.

## Acceptance criteria

- [ ] Browser flow: create products (one goods, one service) → build an invoice mixing both with a custom line → description and VAT locked on catalog lines → issue → the read-only view shows product codes
- [ ] Change a product's price after creating a draft; the draft line keeps its price
- [ ] Every raw-SQL probe in Task 5 behaves as specified
- [ ] Concurrent registration and concurrent product-code creation never return 500
- [ ] Migration chain upgrades on an empty DB, round-trips, and upgrades cleanly on top of a populated Phase 4 database (additive, so no guard)
- [ ] All prior tests green; lint, typecheck, test and build green on both backend and frontend; CI green
- [ ] No new dependencies

## Do NOT

- No quantities or stock, units of measure, price lists, per-client pricing, or discounts.
- No bulk import/export of products.
- No product categories or images.
- No changes to `vat.py` or the rounding rules.
- No PDF work (Phase 6).

## Deliverable

Feature branch `phase-5-catalog`, PR to `main` titled "Phase 5: product & service catalog", green CI. The PR description lists deviations and includes:
- a grep proof that every product query is owner-filtered;
- a list of the raw-SQL probes run, with their results.
