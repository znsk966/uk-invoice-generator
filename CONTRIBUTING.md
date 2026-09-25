# Contributing

Thanks for your interest in **uk-invoice-generator**.

## Ground rules

- **Issues welcome.** Bug reports, questions, and ideas are all appreciated —
  open an issue.
- **PRs need green CI.** All pull requests target `main` and must pass CI
  (backend lint + tests, frontend lint + typecheck + build) before merge.
- **[`CLAUDE.md`](CLAUDE.md) is not negotiable.** It holds the project law:
  Decimal-only money, VAT rounded per rate group, the server computes and the
  client displays, issued invoices immutable, gapless numbering allocated only
  at issue, archive-never-delete, effective-dated VAT rates. Each rule is there
  because it prevents a real bug. A PR that weakens one will be asked to change,
  no matter how convenient the shortcut looks.
- **Money-related code requires tests.** Anything touching money, VAT, or
  numbering needs tests for the edge cases — not just a happy path. This is
  reviewed line by line. [docs/TESTING.md](docs/TESTING.md) lists the tests that
  set the bar.
- **Docs are part of the PR.** If a change alters behaviour a stranger would
  need to know about — a rule, an error code, the snapshot shape, the test
  strategy — update the relevant file under [`docs/`](docs/) in the same PR.

## Running the checks

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

### The test tiers

```bash
cd backend
pytest tests/unit    # money, VAT engine, numbering format, model guards — no DB
pytest tests/db      # rate lookup, gapless allocation, locking — needs a DB
pytest tests/api     # full HTTP lifecycle, error codes, triggers — needs a DB
pytest               # everything
```

The DB and API tiers need `TEST_DATABASE_URL` pointing at a **throwaway**
database:

```bash
createdb -U postgres -O uk_invoice_user uk_invoice_test
export TEST_DATABASE_URL='postgresql+psycopg://uk_invoice_user:YOUR_PASSWORD@localhost:5432/uk_invoice_test'
```

Without it those tiers **skip** rather than fall back to `DATABASE_URL` — the
fixtures drop every table they manage, so they must never be able to reach your
working database. Full details, including why the API tier commits for real:
[docs/TESTING.md](docs/TESTING.md).

## Where to start reading

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layers, module map, transaction
  and error models.
- [docs/MONEY.md](docs/MONEY.md) — the money doctrine and why it is shaped this
  way.
- [docs/INVOICING.md](docs/INVOICING.md) — lifecycle, numbering, snapshots,
  immutability.

## The prompt-driven workflow

This is a proof of concept built through a prompt-driven workflow: each unit of
work is specified as a prompt in [`prompts/`](prompts/) before any code is
written, executed on a feature branch, reviewed, and committed alongside the
code it produced. Contributions do not have to follow that process — a normal PR
is fine — but it explains why the repo is shaped the way it is.
