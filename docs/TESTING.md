# Testing

54 tests in three tiers. The tier a test belongs to is decided by what it needs,
not by what it is about.

| Tier | Path | Count | Needs a database | Covers |
| --- | --- | --- | --- | --- |
| Unit | `tests/unit/` | 23 | no | Money primitives, the VAT engine, number formatting, the model float guards. |
| DB | `tests/db/` | 8 | yes | Effective-dated rate lookup, gapless allocation, row locking. |
| API | `tests/api/` | 21 | yes | The full HTTP lifecycle, error codes, snapshots, the immutability triggers. |
| — | `tests/test_health.py` | 2 | no | `/health`, including the database-unavailable path. |

Run everything:

```bash
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://uk_invoice_user:YOUR_PASSWORD@localhost:5432/uk_invoice_test'
pytest
```

Run one tier: `pytest tests/unit`, `pytest tests/db`, `pytest tests/api`.

## Dependency rules between tiers

- **Unit tests touch no database and no HTTP.** `app/core/money.py` and
  `app/core/vat.py` are pure by design precisely so the arithmetic that matters
  most can be tested with nothing else running. If a change makes the VAT engine
  need a session, the change is wrong.
- **DB tests use the ORM and real SQL, never the app.** They exist for behaviour
  the database owns: locking, constraints, effective-dating.
- **API tests drive the real ASGI app** over `TestClient` and assert on status
  codes, machine error codes, and response bodies. A handful deliberately bypass
  the API and issue raw SQL, to prove the triggers fire independently of it.

## The `TEST_DATABASE_URL` safety rule

DB and API tests read `TEST_DATABASE_URL` from the environment. **If it is
unset, they skip** — with a message saying why — rather than falling back to
`DATABASE_URL`.

That is deliberate and worth keeping. The session fixture starts by dropping
every table it manages. Falling back to the app's configured database would mean
a bare `pytest` silently destroying a developer's working data. There is no
fallback, and there should never be one.

`TEST_DATABASE_URL` must point at a **throwaway** database. Never point it at
`uk_invoice_db` or anything you would miss.

Create the test database once (Windows, host PostgreSQL — the same command works
from bash/WSL):

```bash
createdb -U postgres -O uk_invoice_user uk_invoice_test
```

Without `TEST_DATABASE_URL`, `pytest` still runs the 25 unit and health tests
and reports the rest as skipped. In CI both variables point at the disposable
`postgres:17` service container, so all three tiers always run there.

## Two isolation strategies, one database

The schema is built once per session in `backend/tests/conftest.py`: tables from
the models' metadata, plus the immutability triggers — imported from
`app.modules.invoices.immutability`, the same constant the Alembic migration
executes, so the tests exercise the DDL that production actually runs.

Isolation then differs by tier, because the tiers need opposite things.

**DB tier — savepoint rollback.** `db_session` opens a connection, begins a
transaction, and binds a `Session` with
`join_transaction_mode="create_savepoint"`. Whatever the test does is rolled
back afterwards. Fast, and it leaves no residue.

**API tier — real commits plus truncation.** `TestClient` drives the real app,
whose `get_session` dependency commits per request. Rollback-based isolation
cannot be used here, and not merely as a matter of convenience:

- `SELECT ... FOR UPDATE` and gapless numbering across two separate issues are
  about what survives a **commit**. Wrapping everything in one rolled-back
  transaction would test a scenario that never occurs in production.
- The immutability triggers fire on committed rows reached from a separate
  connection. The raw-SQL trigger probes are on a different connection from the
  request that created the data; inside a single uncommitted transaction they
  would not see that data at all.

So the API tier commits for real and isolates by truncation: an autouse fixture
truncates every mutable table (`RESTART IDENTITY CASCADE`) and re-seeds the four
VAT rates before each test.

**Teardown truncates but does not re-seed.** That asymmetry is load-bearing. An
earlier version re-seeded on teardown too, and the leftover rows collided with
the DB tier, which manages its own `vat_rate` rows and expects an empty table —
`duplicate key (code, valid_from)=(reduced, 2011-01-04)`. Leave teardown as a
plain truncate.

The API tier also overrides `get_session` to bind to the **test** engine, so an
API test can never reach the dev database even if `DATABASE_URL` is set.

## Don't mix pytest-built and Alembic-built schemas

The test fixture builds the schema from model metadata (`create_all`) — it does
not migrate. It also drops only the tables it knows about, and `alembic_version`
is not one of them.

Point Alembic at a database that pytest has used and you get a stale
`alembic_version` describing a schema that is no longer there — the classic
symptom being a migration that thinks it has already run, or
`DuplicateObject: type "vat_rate_code" already exists` on the way back up.

Use separate databases for the two, or rebuild before switching:

```bash
psql -U uk_invoice_user -h localhost -d uk_invoice_test \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

CI sidesteps the whole problem by running the migration round-trip
(`alembic upgrade head` then `alembic downgrade base`) on the empty service
database *before* pytest, which leaves it empty again for the test tier.

## What a money change has to come with

Per [CONTRIBUTING.md](../CONTRIBUTING.md), anything touching money, VAT, or
numbering needs tests for the edge cases — and edge cases specifically, not just
a happy path. The existing suite is the standard to match:

- `test_round_money_classic_float_trap` — the `2.675` case, in the assertion.
- `test_per_group_rounding_differs_from_per_line` — asserts both the correct
  per-group figure and the wrong per-line one, so the divergence is documented.
- `test_failed_issue_does_not_burn_a_number` — a failed issue, then a successful
  one that still gets `00001`.
- `test_float_in_json_parses_exactly_and_snapshot_stores_strings` — a JSON float
  in, exact `Decimal` out, and `jsonb_typeof(...) = 'string'` in the database.
