# PROMPT-04A — Documentation Pass: Phases 0–2

## Context

Phases 0–2 are merged: scaffold + CI, domain models + money core, and the full API with issue/snapshot/immutability. Before the frontend lands (PROMPT-04), fully document what exists. This is a public open source repo — the documentation is written for a stranger who just found it, not for us.

**This is a docs-only PR.** The only permitted changes to Python/TS files are added or improved docstrings and comments. Zero behavior changes: `git diff` on any source file must show documentation-only hunks. All existing tests must pass untouched.

Source of truth is the **code as merged**, not the prompts. Where a prompt and the implementation differ (there were reviewed deviations), document reality. Read the code before writing a single line of docs.

## Task 1 — README overhaul

Restructure `README.md` for a first-time visitor:

- What this is (open source UK invoice generator PoC) and current status: **Phase 2 complete — backend feature-complete; frontend is Phase 3, in progress**.
- Feature list of what actually works today: clients (archive semantics), company profile, invoice drafts, server-computed VAT totals, issue with gapless per-year numbering, versioned snapshots, void, three-layer immutability.
- A short "How it's built" section: the prompt-driven workflow, prompts committed in `prompts/`, review process — this repo's distinguishing feature; link the prompts.
- Quickstart, verified by actually following it: Windows + host PostgreSQL setup, `.env`, migrations, run backend, run tests (with the `TEST_DATABASE_URL` rule), run frontend scaffold.
- A 60-second API tour: one curl sequence that goes profile → client → draft → totals → issue → GET (snapshot), with real request/response fragments generated against the running app.
- Links into `docs/`.

## Task 2 — docs/ARCHITECTURE.md

- Layer diagram (Mermaid — GitHub renders it): router → service → core (`money`/`vat`/`numbering`) → models → PostgreSQL, and where Alembic and the triggers sit.
- Module map: every `app/modules/*` and `app/core/*` file, one line each on its responsibility.
- The transaction model: `get_session` (one transaction per request, commit-on-success), why services never commit, and how that makes issue atomic.
- The error model: `AppError`, the `{"detail": {"code", "message"}}` shape, and the machine-code table.

## Task 3 — docs/MONEY.md

The money doctrine, with rationale — this is the document a skeptical accountant or contributor reads first:

- Decimal-only, `ROUND_HALF_UP`, the float ban and its three enforcement layers (`as_decimal`/`round_money`, the `@validates` model hooks, string money in JSON/snapshots).
- The rounding order: line net first (2 dp), then VAT once per rate group. Include the worked divergence example from the test suite (nine × £0.03 at 20%: per-line 0.09 vs per-group 0.05) with the arithmetic shown.
- Numeric precision table (money 12,2 / unit price 12,4 / quantity 12,3 / rate 5,4) and why.
- Effective-dated VAT rates, `rates_on`, and rates-at-the-tax-point semantics.

## Task 4 — docs/INVOICING.md

The domain rules:

- Lifecycle state machine (Mermaid): draft → issued → void, with what's allowed in each state (including the one legitimate delete: drafts).
- Gapless numbering: per-year sequences, `INV-{year}-{seq:05d}`, `SELECT FOR UPDATE`, the rollback-returns-the-number contract, and why voided numbers stay consumed.
- The snapshot: field-by-field reference of shape v1 (copy a real snapshot from a test run, redact nothing — it's demo data), the write-once rule, money-as-strings, and the version-bump policy.
- Immutability's three layers: schema shape (drafts store inputs only), service 409s, and the DB triggers — including exactly what the triggers block (line INSERT/UPDATE/DELETE on non-drafts, invoice UPDATE outside issued→void, invoice DELETE of non-drafts).
- A short "UK invoice requirements" section mapping each legal content requirement to where it lives in the snapshot/PDF-to-be.

## Task 5 — docs/TESTING.md

- The three tiers (unit / db / api), what each covers, and the dependency rules between them.
- The `TEST_DATABASE_URL` safety rule: why DB tests skip without it and must never point at a dev database; how to create `uk_invoice_test` locally on Windows.
- Why API-tier tests use committing sessions + TRUNCATE (row locks and triggers need real commits) while db-tier tests use savepoint rollback.
- One warning from review experience: don't mix pytest-built schemas and Alembic-built schemas in the same database (`alembic_version` desync); use separate databases or rebuild.

## Task 6 — Housekeeping

- Update `docs/PHASE-PLAN.md`: mark Phases 0–2 done with links to PRs #1–#3; note reviewed deviations (dedicated DB user, committing-session test strategy, trigger scope extension).
- `CONTRIBUTING.md`: expand slightly — how to run each test tier, the docs-are-part-of-the-PR expectation, and a pointer to CLAUDE.md as the non-negotiable rules.
- Docstring audit: every public function in `app/core/` and `app/modules/*/service.py` has a docstring stating its contract (several already do — fill gaps, match the existing voice, change no signatures).

## Acceptance criteria

- [ ] `git diff main` touches only `.md` files, docstrings, and comments — no logic, signatures, imports, or config
- [ ] All existing tests pass unchanged; CI green
- [ ] Quickstart and curl tour were executed against a real running instance, not written from imagination
- [ ] Mermaid diagrams render on GitHub (check the PR's Files view)
- [ ] Docs describe the merged code, including the reviewed deviations — no aspirational features, no references to unmerged work beyond the phase plan
- [ ] No new dependencies, no new tooling (no docs generators, no mkdocs — plain Markdown in `docs/`)

## Do NOT

- No behavior changes of any kind, however tempting a "quick fix" looks — file an issue instead and note it in the PR description.
- No auto-generated API dumps: the OpenAPI schema at `/docs` already exists; link to it rather than duplicating it into Markdown that will rot.
- No badges beyond CI status, no marketing language. Honest and precise beats impressive.

## Deliverable

Feature branch `docs-phases-0-2`, PR to `main` titled "Docs: full documentation pass for Phases 0–2", green CI, PR description listing any issues discovered-but-not-fixed while documenting.
