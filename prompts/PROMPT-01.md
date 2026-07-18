# PROMPT-01 — Phase 0: Scaffold, CI, Open Source Hygiene

## Context

You are building **uk-invoice-generator**, an open source proof-of-concept invoice generator for the UK market. This is Phase 0 of the phase plan. The repo is public from Day 1 — treat every commit as something strangers will read.

**Stack:** PostgreSQL, Python FastAPI backend (SQLAlchemy 2, Alembic, Pydantic v2), React + Vite + TypeScript + Tailwind CSS v4 frontend.

**Environment facts:**
- Development happens on Windows. PostgreSQL 17 runs on the host at `localhost:5432`. There is NO Docker locally — never require Docker for local dev.
- CI runs on GitHub Actions and uses a Dockerized `postgres:17` service container. CI is authoritative.

## Task 1 — Repository layout

Create this structure:

```
uk-invoice-generator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory, /health endpoint
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings, reads DATABASE_URL
│   │   │   └── db.py            # SQLAlchemy engine + session
│   │   └── modules/             # empty for now, domain modules land in Phase 1
│   ├── alembic/                 # initialized, empty migration history
│   ├── alembic.ini
│   ├── tests/
│   │   └── test_health.py
│   └── pyproject.toml           # deps + ruff + pytest config
├── frontend/                    # Vite + React + TS + Tailwind v4
│   └── src/
│       ├── App.tsx              # placeholder page: project name + link to repo
│       └── shared/              # empty, shared UI lands in Phase 3
├── prompts/
│   └── PROMPT-01.md             # this file, committed verbatim
├── docs/
├── .github/workflows/ci.yml
├── CLAUDE.md
├── LICENSE                      # MIT, copyright holder "Zoran" + year 2026
├── README.md
├── CONTRIBUTING.md
├── .env.example
└── .gitignore
```

## Task 2 — Backend scaffold

- Python 3.12. Dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2`, `alembic`, `pydantic-settings`, `psycopg[binary]`. Dev: `pytest`, `httpx`, `ruff`.
- `GET /health` returns `{"status": "ok", "database": "ok" | "unavailable"}` — it must check DB connectivity but MUST NOT crash the app when the DB is down.
- Alembic wired to `DATABASE_URL` from environment; no models, no migrations yet.
- `.env.example`: `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/uk_invoice_dev`
- `ruff check` and `ruff format --check` pass; `pytest` passes (health endpoint test using httpx ASGI transport, DB check mocked or tolerant).

## Task 3 — Frontend scaffold

- Vite + React 18 + TypeScript strict + Tailwind CSS v4 + eslint.
- One placeholder page rendering the project name and a short description.
- Scripts that must pass: `npm run lint`, `npx tsc --noEmit`, `npm run build`.
- Do not add a router, state library, or component library yet.

## Task 4 — CLAUDE.md (Project Law)

Create `CLAUDE.md` containing, verbatim in spirit:

1. All money is `Decimal` with `ROUND_HALF_UP`. Floats never touch money. VAT rounds per rate group, not per line.
2. The server computes all money; the client only displays server-returned values.
3. Issued invoices are immutable and snapshot seller, client, lines, and rates at issue time.
4. Invoice numbers are gapless and allocated only at issue, inside a transaction. Drafts have no number.
5. Master data (clients, items) is archived, never deleted.
6. UK VAT rates (standard 20%, reduced 5%, zero 0%, exempt) are effective-dated reference data, never hardcoded in business logic.
7. Out of scope for the PoC — never build unless a prompt explicitly says so: multi-tenancy, HMRC / Making Tax Digital, e-invoicing, multi-currency, credit notes, real auth.
8. Workflow: work on feature branches, PR to `main`, CI must be green before merge. Prompts live in `prompts/` and are committed as executed.

## Task 5 — CI (`.github/workflows/ci.yml`)

- Trigger: PRs and pushes to `main`.
- Job `backend`: Ubuntu, `postgres:17` **service container** (user/pass/db matching a CI `DATABASE_URL` env), Python 3.12, install deps, run `ruff check`, `ruff format --check`, `pytest`.
- Job `frontend`: Node 20, `npm ci`, `npm run lint`, `npx tsc --noEmit`, `npm run build`.
- Both jobs required; no warnings-as-errors games yet — keep it simple and green.

## Task 6 — Open source hygiene

- `LICENSE`: MIT.
- `README.md`: what the project is (open source UK invoice generator PoC), honest status ("Phase 0 — scaffold"), stack, local setup for Windows + host Postgres (create DB, copy `.env.example`, run migrations, `uvicorn`, `npm run dev`), phase plan summary with a link to `docs/PHASE-PLAN.md`, and a note that the project is built via a prompt-driven workflow with prompts committed in `prompts/`.
- Copy the phase plan into `docs/PHASE-PLAN.md`.
- `CONTRIBUTING.md`: short — issues welcome, PRs need green CI, money-related code requires tests.
- `.gitignore`: Python, Node, `.env`, editor cruft.

## Acceptance criteria

- [ ] `uvicorn app.main:app` starts on Windows with host Postgres and `/health` returns `ok`
- [ ] `/health` still responds (with `database: unavailable`) when Postgres is stopped
- [ ] `pytest`, `ruff check`, `ruff format --check` green locally and in CI
- [ ] `npm run lint`, `tsc --noEmit`, `npm run build` green locally and in CI
- [ ] CI green on the PR; both jobs required
- [ ] LICENSE, README, CONTRIBUTING, CLAUDE.md, `.env.example` present and accurate
- [ ] No Docker required anywhere in local dev instructions

## Do NOT

- Do not create any domain models, migrations, or endpoints beyond `/health` — that is Phase 1.
- Do not add auth, docker-compose for dev, or deployment config.
- Do not add dependencies beyond those listed without a comment in the PR description explaining why.

## Deliverable

One feature branch `phase-0-scaffold`, one PR to `main` titled "Phase 0: scaffold, CI, open source hygiene", green CI, with a PR description summarizing what was created and any deviations from this prompt.
