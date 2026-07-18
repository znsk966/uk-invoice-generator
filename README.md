# uk-invoice-generator

An open-source **proof-of-concept invoice generator for the UK market**.

> **Status: Phase 0 — scaffold.** This repository currently contains the project
> skeleton only: a FastAPI backend with a `/health` endpoint, a Vite/React
> frontend placeholder page, CI, and open-source hygiene. No invoicing features
> exist yet — see the [phase plan](docs/PHASE-PLAN.md) for what is coming.

The project is public from day one and built through a **prompt-driven
workflow**: each unit of work is specified as a prompt in [`prompts/`](prompts/)
and committed alongside the code it produced.

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 (pydantic-settings)
- **Frontend:** React 18 · Vite · TypeScript (strict) · Tailwind CSS v4
- **Database:** PostgreSQL 17
- **CI:** GitHub Actions (Dockerized `postgres:17` service container; CI is authoritative)

## Local setup (Windows + host PostgreSQL)

Local development targets **Windows with PostgreSQL running on the host** at
`localhost:5432`. **Docker is not required for local development.**

### Prerequisites

- Python 3.12+ (CI uses 3.12)
- Node.js 20+
- PostgreSQL 17 running locally

### 1. Create the database

```powershell
createdb -U postgres -h localhost uk_invoice_dev
```

### 2. Configure the backend

Copy the example environment file and set your database URL:

```powershell
Copy-Item .env.example backend\.env
```

Edit `backend\.env` so `DATABASE_URL` matches your local PostgreSQL credentials.
If your password contains URL-reserved characters (`@ : / ? # [ ]` etc.),
URL-encode them in the value.

### 3. Backend — install, migrate, run

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head   # no migrations yet; wired and ready for Phase 1
uvicorn app.main:app --reload
```

The API is now at http://localhost:8000. Check http://localhost:8000/health —
it returns `{"status": "ok", "database": "ok"}` when PostgreSQL is reachable, and
`{"status": "ok", "database": "unavailable"}` (without crashing) when it is not.

### 4. Frontend — install and run

```powershell
cd frontend
npm install
npm run dev
```

The placeholder page is served at the URL Vite prints (default
http://localhost:5173).

## Project checks

```powershell
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

## Phase plan

The full plan lives in [`docs/PHASE-PLAN.md`](docs/PHASE-PLAN.md).

- **Phase 0 — Scaffold & open-source hygiene** *(current)*: monorepo, `/health`, CI.
- **Phase 1 — Domain & database**: models, migrations, money/VAT/numbering core + tests.
- **Phase 2 — API**: invoice lifecycle (draft → issue → void), immutability, gapless numbering.
- **Phase 3 — Frontend**: clients, invoice editor, issue flow, company settings.
- **Phase 4 — PDF & polish**: WeasyPrint UK-compliant invoice PDF from the immutable snapshot.

## Project Law

Core rules that all code must follow — money is `Decimal` computed on the server,
issued invoices are immutable, and more — are documented in
[`CLAUDE.md`](CLAUDE.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issues welcome; PRs need green CI; money-related code requires tests.

## License

[MIT](LICENSE).
