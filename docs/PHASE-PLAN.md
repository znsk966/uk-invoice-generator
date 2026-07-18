# UK Invoice Generator — Phase Plan (PoC)

**Repo:** public from Day 1 · open source (MIT recommended — confirm)
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

## Phase 0 — Scaffold & Open Source Hygiene  *(PROMPT-01)*

- Monorepo: `backend/` (FastAPI, health endpoint, Alembic wired, pytest, ruff) + `frontend/` (Vite + React + TS + Tailwind, placeholder page, eslint, `tsc --noEmit`)
- `prompts/` folder, `CLAUDE.md` with Project Law, `.env.example` for host Postgres
- Open source files: `LICENSE` (MIT), `README.md` with vision + local setup, `CONTRIBUTING.md` stub, `.gitignore`
- GitHub Actions CI: `postgres:17` service container; backend lint + tests, frontend lint + typecheck + build; must be green on the first PR

**Done when:** `uvicorn` serves `/health`, Vite dev page loads, CI green on PR #1.

## Phase 1 — Domain & Database  *(PROMPT-02)*

- SQLAlchemy models + Alembic migrations: `company_profile` (seller: name, address, VAT reg no, bank details), `client`, `vat_rate` (effective-dated), `invoice`, `invoice_line`
- Shared money core: `money.py` (Decimal helpers), `vat.py` (per-rate-group engine), `numbering.py` (gapless allocator)
- Unit tests for rounding edge cases and the VAT engine — this is the line-by-line review target

**Done when:** migrations run clean on empty DB; money/VAT/numbering tests pass with documented edge cases.

## Phase 2 — API  *(PROMPT-03)*

- CRUD: clients (archive semantics), company profile, invoice drafts with lines
- Draft lifecycle: create → edit → **issue** (number allocation + snapshot + immutability enforced at DB and API level) → void
- Server-computed totals endpoint used by drafts; OpenAPI schema clean
- Integration tests: issuing twice, editing after issue (must 409), gapless numbering under concurrency

**Done when:** full invoice lifecycle works via OpenAPI docs UI; immutability tests pass.

## Phase 3 — Frontend  *(PROMPT-04)*

- Client list + form (archive, not delete)
- Invoice editor: line items, VAT rate picker, totals rendered from server response (debounced compute call)
- Issue flow with confirmation; issued invoices render read-only
- Company profile settings page

**Done when:** a person can create a client, build an invoice, issue it, and see it locked — all through the UI.

## Phase 4 — PDF & Polish  *(PROMPT-05)*

- WeasyPrint invoice PDF meeting UK legal content requirements: unique sequential number, invoice date + tax point, seller name/address/VAT number, client details, per-line description/qty/unit price, per-rate VAT breakdown, totals ex-VAT / VAT / gross
- Download from UI; PDF rendered from the immutable snapshot, never live data
- Windows note: WeasyPrint tests skip locally (GTK), CI authoritative — same policy as mk-erp
- README polish, screenshots, demo seed data script

**Done when:** issued invoice downloads as a compliant PDF generated from snapshot data.

---

## Stretch (post-PoC, only if it earns it)

Single-user auth, invoice email delivery, credit notes, CSV export, hosted demo.
