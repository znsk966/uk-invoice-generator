# PROMPT-05 — Phase 4: Auth & Per-User Ownership

## Precondition

PRs #6, #4, #5 are merged to `main` in that order (the known docstring conflict in #5 resolves with #5's wording). Do not start this on an unmerged train.

## Context

The PoC is graduating: registration/login/logout, and **per-user data isolation** — each user has their own clients, company profile, invoices, and numbering. This supersedes Project Law rule 7's "no real auth" (amended in Task 6). The isolation rule is now law: **every domain query is scoped to the authenticated owner; cross-owner access of any kind is a bug.**

No production data exists (pre-1.0 PoC), so the migration may require an empty database rather than backfilling — see Task 2.

## Task 1 — Auth foundation (backend)

- New dependency (the only one): `argon2-cffi`. Passwords hashed with argon2id, library defaults.
- **`user`** model (module `auth`): `email` (unique, lowercased on write), `password_hash`, `created_at`.
- **`user_session`** model: `token_hash` (PK — store the SHA-256 of the token, never the token), `user_id` FK, `created_at`, `expires_at` (30 days).
- Cookie: `session` — HTTP-only, `SameSite=Lax`, `Secure` outside dev (config flag), path `/`. Value is a `secrets.token_urlsafe(32)` random token; only its hash is stored.
- Endpoints under `/api/v1/auth`:
  - `POST /register` — email + password (min length 10, no other complexity rules). Duplicate email → 409 `email_taken`. On success: create user, create session, set cookie (register = logged in).
  - `POST /login` — verify via argon2; **uniform** 401 `invalid_credentials` whether the email or the password was wrong. On success: new session + cookie.
  - `POST /logout` — delete the session row (real revocation), clear the cookie. Idempotent.
  - `GET /me` — current user (id, email) or 401 `not_authenticated`.
- `current_user` dependency: reads the cookie, hashes, looks up an unexpired session, loads the user; else 401 `not_authenticated`. Every domain router now depends on it.
- Out of scope, stated in the auth module docstring so nobody wonders: email verification, password reset, OAuth, roles, rate limiting (self-hosted PoC; a public deployment needs a reverse-proxy rate limit — note it in the README).

## Task 2 — Ownership schema (migration)

One migration, which **aborts with a clear error if any domain table has rows** ("pre-1.0: recreate the database; no data migration path") — document that in the migration docstring and the PR description.

- `owner_id` FK (`user.id`, `ON DELETE RESTRICT`, NOT NULL, indexed) on: `company_profile`, `client`, `invoice`, `number_sequence`, and any future domain table (this is now the template).
- `company_profile`: drop the `CHECK (id = 1)` singleton; replace with `UNIQUE (owner_id)` — singleton **per user**. Plain autoincrement id.
- `invoice.number`: the partial unique index becomes `UNIQUE (owner_id, number) WHERE number IS NOT NULL` — numbers are per-user sequences, so two users legitimately both hold `INV-2026-00001`.
- `number_sequence`: PK becomes composite `(owner_id, key)`. `allocate_number(session, owner_id, key)` signature changes accordingly; same `FOR UPDATE` + rollback-returns-the-number contract, now per owner.
- `vat_rate` stays **global** — UK rates are universal reference data, not user data.
- Immutability triggers: unchanged in behavior; verify they still round-trip in the migration chain.

## Task 3 — Ownership enforcement (services & routers)

- Every service function gains an `owner_id` (or `user`) parameter; every lookup filters by it. A resource belonging to another user returns **404 `not_found`, never 403** — existence must not leak across owners.
- `issue_invoice` resolves the company profile **by owner**, allocates from the **owner's** sequence, and snapshots as before (snapshot shape unchanged — no owner data inside it beyond what seller/client already carry; no version bump needed).
- Grep proof for the PR: every `select(`/`session.get(` on a domain model in services/routers is owner-filtered or reached through an owner-filtered load.

## Task 4 — Frontend

- `/login` and `/register` pages (email, password; register also confirms password client-side — presence check only, no strength meter).
- Auth state via a `useMe()` React Query hook on `GET /me`. Route guard: unauthenticated users are redirected to `/login` (with return-to); authenticated users visiting `/login`/`/register` are redirected to `/invoices`.
- The shared `request()` wrapper: on 401 from any endpoint, invalidate the me-query and redirect to `/login`. `credentials: "include"` everywhere.
- Sidebar footer: current user's email + Logout button.
- No token handling anywhere in JS — the cookie is HTTP-only; the frontend never sees or stores a credential beyond the login form's transient state.

## Task 5 — Tests

- Auth unit/API: register → cookie set → `/me` works; duplicate email 409; wrong password and unknown email both return the identical 401 body; logout revokes (the old cookie gets 401 afterward — proves server-side revocation, not just cookie clearing); expired session 401.
- **Cross-user isolation battery** (the heart of this PR): user A creates client + profile + draft + issues it; user B (fresh session) — lists are empty; GET/PUT/DELETE/issue/void on A's invoice → 404; GET on A's client → 404; B's `company-profile` → 404 `company_profile_missing` until B creates their own.
- **Numbering independence:** A issues → `INV-2026-00001`; B issues → `INV-2026-00001` (same number, different owner — the test that proves per-owner sequences); A issues again → `INV-2026-00002`.
- All existing API tests updated to authenticate first (a `login_as` test helper).
- Frontend (msw): guard redirects when `/me` 401s; login form error rendering; logout clears state.

## Task 6 — Docs & law

- CLAUDE.md: amend rule 7 (auth is now in scope; still out: email verification, password reset, OAuth, roles). Add rule 9: the ownership law — every domain query owner-scoped, cross-owner is 404, new domain tables get `owner_id` from birth.
- README: registration flow in the quickstart, the reverse-proxy rate-limiting note, updated curl tour (login first, cookie jar).
- docs/ARCHITECTURE.md: auth section (session model, cookie, current_user). docs/PHASE-PLAN.md: renumber — this is Phase 4; products = Phase 5; PDF = Phase 6.

## Acceptance criteria

- [ ] Full flow in the browser: register → build and issue an invoice → logout → login as a second user → empty app, own profile, own `INV-2026-00001`
- [ ] Cross-user isolation battery and numbering-independence tests green
- [ ] Old cookie after logout → 401 (server-side revocation proven)
- [ ] Migration aborts loudly on a non-empty database; clean on empty; full chain round-trips
- [ ] All prior tests green (now authenticated); lint/typecheck/build green both sides; CI green
- [ ] No token in localStorage/sessionStorage/JS-readable cookies — grep proof
- [ ] Only new dependency: `argon2-cffi`

## Do NOT

- No JWT, no OAuth, no email verification, no password reset, no roles/permissions, no admin UI, no multi-workspace/teams.
- No changes to money, VAT, numbering internals beyond the owner parameter, or snapshot shape.
- No products/catalog work — that's PROMPT-06.

## Deliverable

Feature branch `phase-4-auth-ownership`, PR to `main` titled "Phase 4: auth & per-user ownership", green CI, PR description with deviations, the owner-filter grep proof, and the no-client-side-token grep proof.
