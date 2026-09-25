# uk-invoice-generator

An open-source **proof-of-concept invoice generator for the UK market**: draft an
invoice, let the server compute the VAT, issue it against a gapless number, and
keep the issued document immutable forever after.

> **Status: Phase 2 complete — the backend is feature-complete.** The full
> invoice lifecycle works end to end over the API. The frontend is a Vite/React
> **scaffold only**; building it is Phase 3, and PDF generation is Phase 4. See
> the [phase plan](docs/PHASE-PLAN.md).

## What works today

- **Clients** — create, edit, archive, unarchive. Never deleted, so issued
  invoices keep valid references.
- **Company profile** — the seller's details, including bank details, as a
  single record.
- **Invoice drafts** — lines with quantity, unit price, and VAT rate code.
  Drafts store inputs only: no number, no stored money.
- **Server-computed VAT** — `Decimal` throughout, `ROUND_HALF_UP`, rounded **per
  rate group** rather than per line. Money crosses JSON as strings, never as
  floats.
- **Issue** — allocates a gapless per-year number (`INV-2026-00001`) inside the
  request transaction, resolves VAT rates at the tax point, and freezes a
  versioned snapshot of seller, client, lines, rates, and totals.
- **Void** — withdraws an issued invoice, keeping its number and snapshot
  intact.
- **Immutability in three layers** — the schema stores no computed money to go
  stale, the service returns 409 on any non-draft mutation, and PostgreSQL
  triggers reject the write even if something bypasses the API entirely.

Out of scope for the PoC, deliberately: multi-tenancy, HMRC / Making Tax
Digital, e-invoicing, multi-currency, credit notes, and real authentication.

## How it's built

This repo is built through a **prompt-driven workflow**, which is the part most
worth a look if you found it by accident.

Each unit of work is specified as a prompt in [`prompts/`](prompts/) — scope,
acceptance criteria, and an explicit "do not build" list — before any code is
written. Claude Code executes the prompt on a feature branch, the result is
reviewed (money-critical code line by line), and the prompt is committed
alongside the code it produced. So every phase can be read as: what was asked
for, what was built, what review changed.

- [`prompts/PROMPT-01.md`](prompts/PROMPT-01.md) — scaffold & CI → PR #1
- [`prompts/PROMPT-02.md`](prompts/PROMPT-02.md) — domain, money/VAT/numbering core → PR #2
- [`prompts/PROMPT-03.md`](prompts/PROMPT-03.md) — the API → PR #3

Review changed real things. The float ban gained a third enforcement layer after
a reviewer showed the model boundary silently accepted `unit_price=0.1`, and the
immutability triggers gained INSERT and DELETE coverage after a reviewer got a
line onto an issued invoice with raw SQL. Both stories are in
[MONEY.md](docs/MONEY.md) and [INVOICING.md](docs/INVOICING.md).

The rules that constrain every change live in [`CLAUDE.md`](CLAUDE.md) — the
project law. They are binding, and they exist because each one prevents a real
bug.

## Stack

- **Backend:** Python 3.12+ · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2
- **Frontend:** React 18 · Vite · TypeScript (strict) · Tailwind CSS v4 *(scaffold)*
- **Database:** PostgreSQL 17
- **CI:** GitHub Actions (Dockerized `postgres:17` service container; CI is authoritative)

## Quickstart

Local development targets **Windows with PostgreSQL running on the host** at
`localhost:5432`. **Docker is not required locally.** The commands below are
shown for bash (Git Bash or WSL); PowerShell equivalents differ only in how
environment variables are set.

### Prerequisites

- Python 3.12+ (CI uses 3.12)
- Node.js 20+
- PostgreSQL 17 running locally

### 1. Create the database and app user

```bash
psql -U postgres -h localhost -c "CREATE ROLE uk_invoice_user WITH LOGIN PASSWORD 'CHANGE_ME';"
psql -U postgres -h localhost -c "CREATE DATABASE uk_invoice_db OWNER uk_invoice_user;"
psql -U postgres -h localhost -d uk_invoice_db -c "ALTER SCHEMA public OWNER TO uk_invoice_user;"
```

### 2. Configure the backend

```bash
cp .env.example backend/.env
```

Edit `backend/.env` so `DATABASE_URL` matches your credentials. If the password
contains URL-reserved characters (`@ : / ? # [ ]`), URL-encode them.

### 3. Backend — install, migrate, run

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows; use .venv/bin/activate elsewhere
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

`alembic upgrade head` applies three migrations: the schema, the UK VAT rate
seed, and the immutability triggers.

The API is now at http://localhost:8000, with interactive OpenAPI docs at
**http://localhost:8000/docs** — the authoritative endpoint reference.
http://localhost:8000/health returns `{"status":"ok","database":"ok"}` when
PostgreSQL is reachable, and reports `"database":"unavailable"` without crashing
when it is not.

### 4. Tests

```bash
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://uk_invoice_user:CHANGE_ME@localhost:5432/uk_invoice_test'
pytest
```

Create that throwaway database once with
`createdb -U postgres -O uk_invoice_user uk_invoice_test`.

**Without `TEST_DATABASE_URL` the database-backed tests skip rather than run.**
That is a safety rule: the fixture drops every table it manages, so it must
never be able to fall back to your real `DATABASE_URL`. Details in
[TESTING.md](docs/TESTING.md).

### 5. Frontend (scaffold)

```bash
cd frontend
npm install
npm run dev
```

This currently serves a placeholder page at http://localhost:5173. The UI is
Phase 3.

## A 60-second API tour

Every response below is real output from a freshly migrated instance, not an
illustration. Set `A=http://localhost:8000/api/v1` first.

**1. Save the seller's profile** (required before anything can be issued):

```bash
curl -s -X PUT $A/company-profile -H 'Content-Type: application/json' -d '{
  "trading_name": "Bramble Studio Ltd",
  "address_line1": "12 Fenchurch Avenue",
  "city": "London",
  "postcode": "EC3M 5BN",
  "vat_number": "GB123456789",
  "bank_account_name": "Bramble Studio Ltd",
  "bank_sort_code": "04-00-04",
  "bank_account_number": "12345678"
}'
```

**2. Create a client:**

```bash
curl -s -X POST $A/clients -H 'Content-Type: application/json' -d '{
  "name": "Harbour Analytics Ltd",
  "address_line1": "4 Dock Road",
  "city": "Bristol",
  "postcode": "BS1 6EG",
  "vat_number": "GB987654321"
}'
```

```json
{"name":"Harbour Analytics Ltd", ..., "id":1, "archived_at":null}
```

**3. Create a draft** with two lines at different VAT rates:

```bash
curl -s -X POST $A/invoices -H 'Content-Type: application/json' -d '{
  "client_id": 1,
  "notes": "Q3 engagement",
  "due_date": "2026-08-19",
  "lines": [
    {"position": 1, "description": "Discovery workshop", "quantity": "2.000",  "unit_price": "650.0000", "vat_rate_code": "standard"},
    {"position": 2, "description": "Printed report",     "quantity": "10.000", "unit_price": "12.5000",  "vat_rate_code": "zero"}
  ]
}'
```

```json
{"id":1,"status":"draft","number":null, ...,"snapshot":null,"issued_at":null}
```

A draft has no number and no snapshot. Money is sent and returned as **strings**.

**4. Ask the server for the totals** — the client never computes them:

```bash
curl -s $A/invoices/1/totals
```

```json
{
  "groups": [
    {"code":"standard","rate":"0.2000","net":"1300.00","vat":"260.00","gross":"1560.00"},
    {"code":"zero","rate":"0.0000","net":"125.00","vat":"0.00","gross":"125.00"}
  ],
  "total_net":"1425.00","total_vat":"260.00","total_gross":"1685.00"
}
```

VAT is computed once per rate group, on the group's net — never per line. Why
that distinction matters, with arithmetic: [MONEY.md](docs/MONEY.md).

**5. Issue it:**

```bash
curl -s -X POST $A/invoices/1/issue -H 'Content-Type: application/json' \
  -d '{"invoice_date": "2026-07-20"}'
```

```json
{
  "id":1,"status":"issued","number":"INV-2026-00001",
  "invoice_date":"2026-07-20","tax_point_date":"2026-07-20",
  "snapshot":{"version":1,"number":"INV-2026-00001", ...,
    "totals":{"net":"1425.00","vat":"260.00","gross":"1685.00"}}
}
```

The number was allocated at this moment and not before. The snapshot froze the
seller, the client, the lines, and the rates in force at the tax point.

**6. Read it back** — money comes from the snapshot, never recomputed:

```bash
curl -s $A/invoices/1
```

Now try to change it:

```bash
curl -s -X PUT $A/invoices/1 -H 'Content-Type: application/json' -d '{"client_id":1,"lines":[]}'
```

```json
{"detail":{"code":"invoice_not_draft","message":"Only draft invoices can be edited."}}
```

And bypass the API entirely:

```bash
psql -d uk_invoice_db -c "UPDATE invoice_line SET description='hacked' WHERE invoice_id=1;"
```

```
ERROR:  invoice_line of invoice 1 is immutable (invoice status=issued)
```

The full snapshot, field by field, is in [INVOICING.md](docs/INVOICING.md).

## Documentation

| Document | What's in it |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layers, module map, the transaction model, the error model. |
| [docs/MONEY.md](docs/MONEY.md) | The money doctrine: Decimal-only, the float ban's three layers, rounding order, precision, effective-dated rates. |
| [docs/INVOICING.md](docs/INVOICING.md) | Lifecycle, gapless numbering, the snapshot, immutability, UK invoice content requirements. |
| [docs/TESTING.md](docs/TESTING.md) | The three test tiers, the `TEST_DATABASE_URL` safety rule, isolation strategies. |
| [docs/PHASE-PLAN.md](docs/PHASE-PLAN.md) | What is done, what is next. |
| [CLAUDE.md](CLAUDE.md) | Project law — binding rules for all code here. |

The endpoint reference is the OpenAPI schema at `/docs` on a running instance;
it is not duplicated into Markdown that would rot.

## Project checks

```bash
# Backend
cd backend
ruff check .
ruff format --check .
pytest

# Frontend
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues welcome; PRs need green CI;
money-related code requires tests.

## License

[MIT](LICENSE).
