# Architecture

How the backend is put together, and why. Current as of Phase 4 (auth &
per-user ownership; the backend is feature-complete and there is a working React
frontend — see [PHASE-PLAN.md](PHASE-PLAN.md)). This document covers the backend; the frontend's
one hard rule is that it never does money arithmetic — it renders server-computed
values and asks the server to recompute on every edit (see
[MONEY.md](MONEY.md)).

## Layers

```mermaid
flowchart TD
    HTTP["HTTP client<br/>(curl, /docs, the React frontend)"]
    Router["Routers — app/modules/*/router.py<br/>HTTP shape, Pydantic schemas, no logic"]
    Service["Service — app/modules/invoices/service.py<br/>domain rules, AppError, never commits"]
    Core["Core — app/core/<br/>money · vat · numbering · errors · db"]
    Repo["Repository — app/modules/vat/repository.py<br/>effective-dated rate lookup"]
    Models["Models — app/modules/*/models.py<br/>SQLAlchemy 2, @validates float guards"]
    PG[("PostgreSQL 17")]
    Alembic["Alembic — backend/alembic/versions/<br/>schema · VAT seed · triggers"]
    Trig["Immutability triggers<br/>app/modules/invoices/immutability.py"]

    HTTP --> Router --> Service
    Service --> Core
    Service --> Repo
    Service --> Models
    Repo --> Models
    Models --> PG
    Alembic -- "builds & seeds" --> PG
    Alembic -- "installs" --> Trig
    Trig -. "guards writes" .-> PG
```

The rule the layering enforces: **money arithmetic happens only in `app/core/`**
(`money.py`, `vat.py`). Routers and models never compute money; services
orchestrate but delegate every calculation to core.

## Module map

### `app/core/`

| File | Responsibility |
| --- | --- |
| `config.py` | `Settings` (pydantic-settings) — `DATABASE_URL` from env / `backend/.env`. |
| `db.py` | Engine, `SessionLocal`, declarative `Base`, the `get_session` request dependency, and `check_db()` for `/health`. |
| `errors.py` | `AppError`, the machine-code constants, and the handlers producing the uniform error body. |
| `mixins.py` | `TimestampMixin` — server-managed `created_at` / `updated_at`. |
| `money.py` | Money primitives: `round_money`, `as_decimal`, `reject_float`, and the precision conventions. See [MONEY.md](MONEY.md). |
| `vat.py` | The pure VAT engine: `VatRateCode`, `LineInput`, `RateGroup`, `InvoiceTotals`, `compute_totals`. No DB access. |
| `numbering.py` | `allocate_number` (gapless, row-locked), `format_invoice_number`, `invoice_sequence_key`. |

### `app/modules/`

| File | Responsibility |
| --- | --- |
| `auth/models.py` | `User` (email + argon2 hash) and `UserSession` (PK = SHA-256 of the cookie token). |
| `auth/security.py` | Password hashing (argon2id) and session-token primitives (random token, SHA-256, expiry). |
| `auth/service.py` | Register / login / logout and session lookup. Uniform 401 on any credential failure. |
| `auth/deps.py` | `current_user` dependency and the session-cookie contract (HTTP-only, SameSite=Lax, Secure outside dev). |
| `auth/router.py` | `/auth` register / login / logout / me — the only endpoints that don't require auth. |
| `clients/models.py` | `Client` — master data with `archived_at` (archive, never delete); `owner_id` FK. |
| `clients/schemas.py` | Client request/response schemas. |
| `clients/router.py` | `/clients` CRUD plus `/archive` and `/unarchive`. |
| `company/models.py` | `CompanyProfile` — the seller; a single row with `id = 1`, enforced by CHECK. |
| `company/schemas.py` | Company profile upsert/read schemas. |
| `company/router.py` | `GET` / `PUT /company-profile`. |
| `invoices/models.py` | `Invoice` and `InvoiceLine` — inputs only, no computed money columns; JSONB `snapshot`; partial unique index on `number`. |
| `invoices/schemas.py` | Invoice schemas; every money field is `Decimal` with `allow_inf_nan=False`. |
| `invoices/service.py` | Draft CRUD, totals (`compute_invoice_totals`, `totals_from_snapshot`), and the money-critical `issue_invoice` / `void_invoice`. |
| `invoices/immutability.py` | The trigger DDL, as a single shared constant (see below). |
| `invoices/router.py` | `/invoices` CRUD plus `/totals`, `/preview-totals`, `/issue`, `/void`. |
| `numbering/models.py` | `NumberSequence` — the persistent per-year counter. |
| `vat/models.py` | `VatRate` — effective-dated reference data; owns the shared `vat_rate_code` Postgres enum. |
| `vat/repository.py` | `rates_on(session, date)` — the applicable rate for every code on a date. |
| `models.py` | Model registry: importing it populates `Base.metadata` for Alembic and the test harness. |
| `main.py` | `create_app()` — mounts `/health` and the routers under `/api/v1`. |

## Two ways to get totals

Money is always computed on the server; there are two endpoints for it because a
saved invoice and an in-progress edit are different situations.

| Endpoint | Reads DB | Persists | Used for |
| --- | --- | --- | --- |
| `GET /invoices/{id}/totals` | yes | no | A saved invoice. **Draft:** computed live from its lines at today's rates. **Issued / void:** returned from the snapshot verbatim (`totals_from_snapshot`), never recomputed — same source as `GET /invoices/{id}`. |
| `POST /invoices/preview-totals` | rates only | no | Unsaved editor edits. Lines are posted in the body; nothing is created or read except the VAT rates. Lets the draft editor show live totals without autosaving on every keystroke. |

Both run the one VAT engine in `app/core/vat.py`, so a preview and the eventual
issued snapshot agree to the penny. `preview-totals` resolves rates at
`on_date` (default today) and returns `422 validation_failed` if no rate is
effective then — the same error surface as issuing before the VAT seed date.

Why the issued path must not recompute: a VAT rate change after issue would make
a live recomputation disagree with the frozen document. The snapshot is the
record; see [INVOICING.md](INVOICING.md#the-snapshot).

## The transaction model

`get_session` (in `app/core/db.py`) is the only place a transaction is opened or
closed:

```python
session = SessionLocal()
try:
    yield session
    session.commit()      # success -> commit, once, at the end of the request
except Exception:
    session.rollback()    # any error -> the whole request is undone
    raise
finally:
    session.close()
```

**One request is one transaction.** Services call `session.flush()` when they
need generated IDs, but they never commit — deliberately. That single rule is
what makes issue atomic:

`issue_invoice` allocates a gapless number partway through its work. If anything
after that point fails — a missing VAT rate, a database error, a bug — the
request's transaction rolls back and the sequence increment rolls back with it.
The number is returned to the sequence rather than burned, and the next issue
reuses it. There is a test for exactly this
(`test_failed_issue_does_not_burn_a_number`).

If a service committed on its own, a later failure would leave a consumed number
with no invoice attached to it — a gap in a sequence that UK invoicing requires
to be gapless. Hence: **services never commit.**

## The error model

Every handled error is rendered as one shape, so a client can branch on a stable
machine code instead of parsing prose:

```json
{"detail": {"code": "invoice_not_draft", "message": "Only draft invoices can be edited."}}
```

Services raise `AppError(status_code, code, message)`; handlers registered by
`register_error_handlers(app)` turn it into that body. Pydantic request
validation failures are collapsed into the same shape with code
`validation_failed`, keeping the full Pydantic error list under an extra
`errors` key for debugging.

| Code | Status | Raised when |
| --- | --- | --- |
| `not_found` | 404 | The invoice, client, or company profile does not exist **for this owner** (another user's resource looks identical to a missing one). |
| `client_archived` | 409 | Creating/editing an invoice for an archived client, or issuing one. |
| `invoice_not_draft` | 409 | Editing, deleting, or issuing an invoice that is not a draft. |
| `invoice_not_issued` | 409 | Voiding an invoice that is not in `issued`. |
| `validation_failed` | 422 | Request body validation, no lines at issue, or no VAT rate at the tax point. |
| `company_profile_missing` | 409/404 | Issuing before the seller's company profile has been saved (409); reading a not-yet-created profile (404). |
| `email_taken` | 409 | Registering an email that already exists. |
| `invalid_credentials` | 401 | Login with a wrong password **or** an unknown email — deliberately identical, so neither is revealed. |
| `not_authenticated` | 401 | No valid session cookie on a protected endpoint. |

The codes are defined once in `app/core/errors.py`; this table mirrors them.

## Authentication & ownership

Added in Phase 4. The app is multi-user: each user owns their clients, company
profile, invoices, and invoice numbering.

**Sessions, not tokens-in-JS.** Login and registration mint a
`secrets.token_urlsafe(32)` token and set it as a cookie: `session`, HTTP-only,
`SameSite=Lax`, `Secure` outside dev (the `COOKIE_SECURE` flag), path `/`. Only
the token's **SHA-256 hash** is stored (`user_session.token_hash`), so a database
leak holds nothing replayable, and the token never touches JavaScript. Passwords
are hashed with **argon2id** (`argon2-cffi`, library defaults).

The `current_user` dependency reads the cookie, hashes it, looks up an unexpired
`user_session`, and loads the `User`; anything missing is a uniform 401
`not_authenticated`. Every domain router depends on it; only `/health` and
`/api/v1/auth/*` are open. Logout **deletes the session row** — real server-side
revocation, not just clearing the cookie — and is idempotent.

**Ownership is enforced in the service/router layer.** Every domain query filters
by `owner_id`; a resource owned by another user returns **404 `not_found`, never
403**, so existence never leaks across accounts (CLAUDE.md rule 9). Numbering is
per owner: `number_sequence` is keyed `(owner_id, key)` and
`allocate_number(session, owner_id, key)` advances each user's sequence
independently, so two users legitimately both hold `INV-2026-00001`. The snapshot
shape is unchanged — it carries no owner data beyond the seller/client copies it
always held.

**Deliberately out of scope** (self-hosted single-user PoC): email verification,
password reset, OAuth, roles/permissions, and rate limiting. A public deployment
must put a reverse-proxy rate limit in front of `/auth`.

## Migrations and triggers

Four migrations, applied in order:

1. `5f7da3d0e4dd` — schema: company profile, clients, VAT rates, invoices, numbering.
2. `de303147f0cb` — seed: the four UK VAT rates, effective 2011-01-04, open-ended.
3. `14438b1216ca` — the immutability triggers.
4. `57924f8aade2` — auth (`user`, `user_session`) and per-user ownership (`owner_id` on the domain tables). **Aborts if any user-owned domain table already has rows** — pre-1.0 has no data-migration path; recreate the database instead.

**Postgres ENUMs need explicit lifecycle management in Alembic.** Autogenerate
renders `sa.Enum(...)` inline per table; `upgrade` then works, but `downgrade`
drops the tables and leaves the enum *types* behind, so a re-`upgrade` fails with
`DuplicateObject`. The schema migration therefore declares each enum at module
level with `create_type=False` and calls `.create(bind, checkfirst=True)` /
`.drop(bind, checkfirst=True)` explicitly. CI runs `alembic upgrade head` then
`alembic downgrade base` on every push to keep this honest.

**The trigger DDL lives in application code, not in the migration.**
`app/modules/invoices/immutability.py` exports `IMMUTABILITY_UP_SQL` and
`IMMUTABILITY_DOWN_SQL`; the migration executes them, and so does the test
harness, which builds its schema from model metadata rather than by migrating.
Two copies of that SQL would eventually drift, and the copy the tests exercised
would not be the copy production ran. Extend the constant rather than adding a
delta migration with divergent SQL.

What the triggers enforce is documented in
[INVOICING.md](INVOICING.md#immutability-in-three-layers).
