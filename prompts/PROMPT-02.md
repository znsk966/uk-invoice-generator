# PROMPT-02 — Phase 1: Domain, Database & Money Core

## Context

Phase 0 (scaffold, CI, open source hygiene) is merged. This phase adds the domain models, Alembic migrations, and the money-critical core modules. **No API endpoints in this phase** — those are Phase 2. Everything here will be reviewed line by line, especially `money.py`, `vat.py`, and `numbering.py`.

Re-read `CLAUDE.md` before starting. The Project Law rules on Decimal-only money, per-rate-group VAT rounding, gapless numbering, snapshots, and archive-not-delete all bind this phase directly.

## Task 0 — Cleanup carried over from the Phase 0 review

1. **Align the config fallback.** `app/core/config.py`'s default `database_url` points at `uk_invoice_dev` with `postgres:postgres`, while `.env.example` and the README use `uk_invoice_db` with a dedicated `uk_invoice_user`. Align the fallback to `postgresql+psycopg://uk_invoice_user:CHANGE_ME@localhost:5432/uk_invoice_db` and add a comment that the real configuration always comes from `backend/.env` / the environment — the fallback exists only so imports never explode.
2. **Make the anyio test dependency explicit.** `@pytest.mark.anyio` currently works only because `anyio`'s pytest plugin arrives transitively via httpx/starlette. Add `anyio` to `[project.optional-dependencies].dev` so a dependency shuffle can never silently break test collection.

## Task 1 — Money core: `app/core/money.py`

- `TWO_PLACES = Decimal("0.01")`, GBP only for the PoC.
- `def round_money(value: Decimal) -> Decimal` — quantize to 2 dp with `ROUND_HALF_UP`. Reject non-Decimal input with `TypeError` (floats must fail loudly, not get converted).
- `def as_decimal(value: str | int | Decimal) -> Decimal` — safe constructor; explicitly rejects `float`.
- Numeric precision conventions (document in the module docstring and use everywhere):
  - money amounts: `Numeric(12, 2)`
  - unit prices: `Numeric(12, 4)`
  - quantities: `Numeric(12, 3)`

## Task 2 — VAT engine: `app/core/vat.py`

- `VatRateCode` enum: `standard`, `reduced`, `zero`, `exempt`.
- Pure function, no DB access:
  ```
  compute_totals(lines: Sequence[LineInput], rates: Mapping[VatRateCode, Decimal]) -> InvoiceTotals
  ```
  where `LineInput` = (quantity, unit_price, vat_rate_code) and `rates` maps code → rate as a fraction (e.g. `Decimal("0.20")`). `exempt` and `zero` both map to `Decimal("0")` but remain distinct codes (they must appear as separate groups on the invoice).
- Algorithm, exactly this order:
  1. line net = `round_money(quantity × unit_price)` per line (2 dp).
  2. Group lines by `vat_rate_code`; per group: `net = Σ line nets`, `vat = round_money(net × rate)`. **VAT is computed once per rate group on the group net — never per line.**
  3. `gross = net + vat` per group; invoice totals = sums of the group values.
- Return a frozen dataclass: per-group breakdown (code, rate, net, vat, gross) ordered standard → reduced → zero → exempt, plus invoice-level `total_net`, `total_vat`, `total_gross`. This structure is what the API (Phase 2) and the PDF (Phase 4) will render — get the shape right now.

## Task 3 — Models & migrations

SQLAlchemy 2 declarative models under `app/modules/`, one module per aggregate, with `Base` in `app/core/db.py`. Alembic autogenerate is now wired (`target_metadata` set). Two migrations: (1) schema, (2) data seed for VAT rates.

- **`company_profile`** (module `company`): trading name, address lines 1–2, city, postcode, country (default `GB`), `vat_number` (nullable — not every business is VAT-registered), `company_number` (nullable), email, phone, bank account name / sort code / account number (all nullable). Enforce single row: `id` integer PK with a `CHECK (id = 1)` constraint.
- **`client`** (module `clients`): name, address lines, city, postcode, country default `GB`, `vat_number` nullable, email nullable, `archived_at` timestamptz nullable — **archive semantics, no hard delete anywhere in this codebase.**
- **`vat_rate`** (module `vat`): `code` (enum above), `rate` `Numeric(5, 4)` as a fraction, `valid_from` date, `valid_to` date nullable. Unique constraint on `(code, valid_from)`. Seed migration inserts the current UK rates valid from `2011-01-04`, open-ended: standard `0.2000`, reduced `0.0500`, zero `0.0000`, exempt `0.0000`.
  - Repository function `rates_on(session, on_date: date) -> Mapping[VatRateCode, Decimal]` — selects the row per code where `valid_from <= on_date` and (`valid_to` is null or `valid_to >= on_date`); raises if any code has no applicable rate.
- **`invoice` + `invoice_line`** (module `invoices`):
  - `invoice`: `status` enum (`draft`, `issued`, `void`), `number` text nullable + partial unique index (`WHERE number IS NOT NULL`), `client_id` FK, `invoice_date` nullable (set at issue), `tax_point_date` nullable, `due_date` nullable, `currency` text default `'GBP'` with `CHECK (currency = 'GBP')`, `notes` text, `snapshot` JSONB nullable, `issued_at` timestamptz nullable, created/updated timestamps.
  - `invoice_line`: FK to invoice (cascade delete **for drafts only in the service layer** — the DB FK itself is plain `ON DELETE CASCADE`; issued invoices are never deleted), `position` int, `description` text, `quantity Numeric(12,3)`, `unit_price Numeric(12,4)`, `vat_rate_code` enum.
  - Drafts store **inputs only** — no computed money columns. Totals are always computed on demand via `vat.py`. At issue (Phase 2), everything is frozen into `snapshot`.
- **`number_sequence`** (module `numbering`): `key` text PK, `next_value` int not null default 1.

## Task 4 — Gapless numbering: `app/core/numbering.py`

- `def allocate_number(session, key: str) -> int` — `SELECT ... FOR UPDATE` on the `number_sequence` row (insert it if missing), return `next_value`, increment. Must run inside the caller's transaction so a rolled-back issue never burns a number — document this contract in the docstring.
- `def format_invoice_number(year: int, seq: int) -> str` → `INV-{year}-{seq:05d}`; sequence key is `invoice-{year}` (per-year reset). UK law requires unique and sequential, which per-year sequences satisfy.

## Task 5 — Tests

Two tiers, cleanly separated:

- **Pure unit tests (no DB):** `money.py` rounding edge cases — `2.675` → `2.68` (the classic float trap; assert the Decimal path gets it right and that passing a `float` raises), negative amounts, already-quantized values. `vat.py`: a documented case where per-rate-group rounding differs from per-line rounding (e.g. many lines of £0.03 at 20%) with both values shown in the test; mixed-group invoice; empty invoice; exempt and zero appearing as distinct groups.
- **DB tests:** read `TEST_DATABASE_URL` from the environment. **If unset, skip with a clear message** — never run destructive table create/drop against `DATABASE_URL`. A `conftest.py` fixture creates all tables at session start and drops them at session end, with per-test transaction rollback.
  - `rates_on` effective-dating: on the boundary date, before it (raises), and with a closed-out rate row.
  - Numbering: sequential allocation, per-year key isolation, and a **concurrency test** — two threads, two sessions, both allocating on the same key; assert no duplicate and no gap. Also: allocate inside a transaction that rolls back, then allocate again — the number must be reused (gapless).
- CI: set `TEST_DATABASE_URL` to the existing `postgres:17` service (`uk_invoice_test`) in `ci.yml` so DB tests run there. Update the README testing section: how to create a local `uk_invoice_test` database and run the full suite on Windows.

## Acceptance criteria

- [ ] `alembic upgrade head` runs clean on an empty database; `alembic downgrade base` also works
- [ ] VAT seed present after migration; `rates_on` returns all four codes for today
- [ ] All unit tests pass without any database; DB tests skip gracefully when `TEST_DATABASE_URL` is unset
- [ ] Full suite (unit + DB) green in CI
- [ ] `ruff check`, `ruff format --check` green; `anyio` now explicit in dev deps
- [ ] Config fallback aligned (Task 0.1)
- [ ] No API routes, schemas, or frontend changes in this PR
- [ ] Grep proof in the PR description: no `float(` anywhere in money paths, no computed money columns on draft tables

## Do NOT

- No FastAPI endpoints, Pydantic schemas, or frontend work — Phase 2/3.
- No issue/snapshot logic yet — Phase 2 (but the `snapshot` column and immutability-ready model shape land now).
- No extra dependencies beyond `anyio` without justification in the PR description.

## Deliverable

Feature branch `phase-1-domain-money-core`, PR to `main` titled "Phase 1: domain models, migrations, money/VAT/numbering core", green CI, PR description listing any deviations and the grep proof from the acceptance criteria.
