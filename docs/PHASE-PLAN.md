# UK Invoice Generator — Phase Plan (PoC)

**Repo:** public from Day 1 · open source (MIT — see [LICENSE](../LICENSE))
**Stack:** PostgreSQL · Python FastAPI (SQLAlchemy 2 + Alembic + Pydantic v2) · React + Vite + TypeScript + Tailwind CSS v4
**Dev environment:** Windows, host PostgreSQL on `localhost:5432`, no Docker locally
**CI:** GitHub Actions with Dockerized PostgreSQL service container — CI is authoritative for anything that can't run on Windows (e.g. WeasyPrint/GTK)
**Workflow:** Claude writes `prompts/PROMPT-NN.md` → Claude Code executes on a feature branch → PR to `main` with green CI → Zoran reviews (money-critical code line by line)

---

## Project Law (goes into CLAUDE.md in Phase 0)

Carried over from mk-erp — these rules exist because they prevent real bugs:

1. **Decimal only.** All money is `Decimal`, `ROUND_HALF_UP`, never float. VAT rounded per rate group, not per line.
2. **Server computes money, client displays.** The frontend never calculates totals; it renders what the API returns.
3. **Issued invoices are immutable.** On issue: snapshot seller, client, lines, rates. Later edits to master data never change an issued invoice.
4. **Numbers allocated only at issue.** Gapless sequential numbering, allocated inside a transaction at the moment of issue — drafts have no number.
5. **Archive, don't delete.** Clients and items are archived, never hard-deleted, so issued invoices keep valid references.
6. **VAT rates are effective-dated reference data**, not hardcoded constants (UK: standard 20%, reduced 5%, zero 0%, exempt).
7. **Out of scope — do not build:** multi-tenancy, Making Tax Digital / HMRC API, e-invoicing, multi-currency, credit notes, auth beyond a single-user stub.

---

## Status

| Phase | Prompt | State | PR |
| --- | --- | --- | --- |
| 0 — Scaffold & OSS hygiene | PROMPT-01 | **Done** | [#1](https://github.com/znsk966/uk-invoice-generator/pull/1) |
| 1 — Domain & database | PROMPT-02 | **Done** | [#2](https://github.com/znsk966/uk-invoice-generator/pull/2) |
| 2 — API | PROMPT-03 | **Done** | [#3](https://github.com/znsk966/uk-invoice-generator/pull/3) |
| 3 — Frontend | PROMPT-04 | **Done** | [#5](https://github.com/znsk966/uk-invoice-generator/pull/5) |
| 4 — Auth & per-user ownership | PROMPT-05 | **Done** | [#8](https://github.com/znsk966/uk-invoice-generator/pull/8) |
| 5 — Products / catalog | PROMPT-06 | **Done** | — |
| 6 — PDF & polish | PROMPT-07 | Not started | — |

A documentation pass (PROMPT-04A, [#4](https://github.com/znsk966/uk-invoice-generator/pull/4))
landed between Phases 2 and 3 — it added the `docs/` set and this table.

**Roadmap renumbered in Phase 4.** PROMPT-05 turned out to be auth & per-user
ownership (it amended Project Law rule 7 to bring real auth in scope and added
rule 9, the ownership law). PDF generation — originally slated as Phase 4 — moves
to Phase 6, with a products/catalog phase (PROMPT-06) now explicit at Phase 5.

### Reviewed deviations from the original plan

Things the phases did differently from this document, each accepted in review:

- **Dedicated database role.** Phase 0 planned to run against a default local
  superuser; the implementation uses a dedicated `uk_invoice_user` owning
  `uk_invoice_db`, with a separate throwaway `uk_invoice_test` for tests.
- **Committing test sessions for the API tier.** The plan assumed one
  rollback-based isolation strategy. The API tier needs real commits — row locks
  and triggers do not behave meaningfully inside a single rolled-back
  transaction — so it isolates by `TRUNCATE` + reseed instead. See
  [TESTING.md](TESTING.md).
- **Trigger scope extended in review.** The immutability triggers originally
  covered `UPDATE` on `invoice` and `invoice_line`. Review demonstrated two
  bypasses with raw SQL, so `INSERT` on `invoice_line` and `DELETE` on `invoice`
  are now guarded too.
- **Float guard at the model boundary.** Not in the original plan. Added in
  Phase 1 after review showed `InvoiceLine(unit_price=0.1)` was silently
  accepted: `reject_float` is now wired via `@validates` on every money,
  quantity, and rate column.
- **Third enforcement point for money-as-strings.** Snapshots store all money as
  JSON strings, asserted at the database level with `jsonb_typeof`.

---

## Phase 0 — Scaffold & Open Source Hygiene  *(PROMPT-01)* — **done**

- Monorepo: `backend/` (FastAPI, health endpoint, Alembic wired, pytest, ruff) + `frontend/` (Vite + React + TS + Tailwind, placeholder page, eslint, `tsc --noEmit`)
- `prompts/` folder, `CLAUDE.md` with Project Law, `.env.example` for host Postgres
- Open source files: `LICENSE` (MIT), `README.md` with vision + local setup, `CONTRIBUTING.md` stub, `.gitignore`
- GitHub Actions CI: `postgres:17` service container; backend lint + tests, frontend lint + typecheck + build; must be green on the first PR

**Done when:** `uvicorn` serves `/health`, Vite dev page loads, CI green on PR #1.

## Phase 1 — Domain & Database  *(PROMPT-02)* — **done**

- SQLAlchemy models + Alembic migrations: `company_profile` (seller: name, address, VAT reg no, bank details), `client`, `vat_rate` (effective-dated), `invoice`, `invoice_line`
- Shared money core: `money.py` (Decimal helpers), `vat.py` (per-rate-group engine), `numbering.py` (gapless allocator)
- Unit tests for rounding edge cases and the VAT engine — this is the line-by-line review target

**Done when:** migrations run clean on empty DB; money/VAT/numbering tests pass with documented edge cases.

## Phase 2 — API  *(PROMPT-03)* — **done**

- CRUD: clients (archive semantics), company profile, invoice drafts with lines
- Draft lifecycle: create → edit → **issue** (number allocation + snapshot + immutability enforced at DB and API level) → void
- Server-computed totals endpoint used by drafts; OpenAPI schema clean
- Integration tests: issuing twice, editing after issue (must 409), gapless numbering under concurrency

**Done when:** full invoice lifecycle works via OpenAPI docs UI; immutability tests pass.

## Phase 3 — Frontend  *(PROMPT-04)* — **done**

- Client list + form (archive, not delete)
- Invoice editor: line items, VAT rate picker, totals rendered from server response (debounced compute call via `POST /invoices/preview-totals`)
- Issue flow with confirmation; issued invoices render read-only from the snapshot
- Company profile settings page

Built with React Router, TanStack Query, and Tailwind v4; every money/quantity/rate
value is carried as a string end to end, and the client never does arithmetic on
it. Tested with Vitest + Testing Library + MSW.

**Done when:** a person can create a client, build an invoice, issue it, and see it locked — all through the UI.

## Phase 4 — Auth & Per-User Ownership  *(PROMPT-05)* — **done**

- Registration, login, logout (argon2id passwords; opaque session token stored only as its SHA-256 hash; HTTP-only `session` cookie, Secure outside dev)
- `current_user` dependency guards every domain endpoint; only `/health` and `/auth/*` are open
- Per-user ownership: `owner_id` on company_profile, client, invoice, number_sequence; company profile is a per-user singleton; invoice numbers unique per owner; numbering keyed `(owner_id, key)`
- Cross-owner access is invisible: 404 `not_found`, never 403
- Frontend: `/login` + `/register`, a route guard, sidebar footer with email + Logout; the shared fetch wrapper sends the cookie and redirects to `/login` on any 401

Amended Project Law: rule 7 (real auth now in scope) and new rule 9 (the ownership law). Out of scope still: email verification, password reset, OAuth, roles.

**Done when:** register → build and issue an invoice → logout → login as a second user → empty app, own profile, own `INV-2026-00001`.

## Phase 5 — Products / Catalog  *(PROMPT-06)* — **done**

- Per-user product & service catalog (owner-scoped from birth — CLAUDE.md rule 9): code, description, kind (goods/service), VAT rate code, default unit price; archive, never delete
- **Product identity is immutable** (code, description, kind, VAT rate); only the price is editable. Amended Project Law rule 5
- Invoice lines optionally **link** a product (`invoice_line.product_id`); the server copies description and VAT from it, and a DB trigger enforces that they match. Ad-hoc lines still work; an invoice can mix both
- Snapshot v2: lines carry `product_id`, `product_code`, `kind` (v1 snapshots stay valid)
- Frontend: `/products` page, price-only edit form, per-line product picker that locks description and VAT
- Phase 4 review fixes: concurrent registration → 409 (never 500); login verifies a dummy hash for unknown emails

Deviation from the original bullet above: lines *link* to catalog items rather than only copying values. Safe because identity is immutable and issued invoices still render from their snapshot.

**Done when:** a user can keep a catalog and build invoice lines from it.

## Phase 6 — PDF & Polish  *(PROMPT-07)* — **not started**

- WeasyPrint invoice PDF meeting UK legal content requirements: unique sequential number, invoice date + tax point, seller name/address/VAT number, client details, per-line description/qty/unit price, per-rate VAT breakdown, totals ex-VAT / VAT / gross
- Download from UI; PDF rendered from the immutable snapshot, never live data
- Windows note: WeasyPrint tests skip locally (GTK), CI authoritative — same policy as mk-erp
- README polish, screenshots, demo seed data script

**Done when:** issued invoice downloads as a compliant PDF generated from snapshot data.

---

## Stretch (post-PoC, only if it earns it)

Invoice email delivery, credit notes, CSV export, hosted demo.
