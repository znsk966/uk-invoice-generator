# PROMPT-04 — Phase 3: Frontend — Clients, Invoice Editor, Issue Flow

## Context

Phases 0–2 are merged: the API is complete (clients, company profile, drafts, server-computed totals, issue/void, snapshot-served money). This phase builds the React UI. The frontend's prime directive, from CLAUDE.md: **the server computes money, the client displays it.** The frontend never performs arithmetic on money — not for totals, not for line nets, not "just for display".

Scaffold already exists: Vite + React 18 + TypeScript strict + Tailwind CSS v4 + eslint.

## Task 0 — One small backend addition (the only backend change allowed)

`POST /api/v1/invoices/preview-totals` — stateless totals preview for the editor. Body: `{ "lines": [{position, description, quantity, unit_price, vat_rate_code}], "on_date": "YYYY-MM-DD" (optional, default today) }`. Returns the same `InvoiceTotals` shape as `GET /invoices/{id}/totals`, computed via `rates_on` + `compute_totals`. Persists nothing. Reuses the existing line schema (string money). Two API tests: happy path matches `compute_totals`; pre-2011 date → 422 `validation_failed`.

This exists so the editor can show live totals for **unsaved** edits without autosaving drafts on every keystroke.

## Task 1 — Frontend foundation

- New dependencies (allowed, nothing else): `react-router-dom`, `@tanstack/react-query`. Dev: `vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`, `msw`.
- Vite dev proxy: `/api` → `http://localhost:8000`.
- `src/api/`: one typed client module per resource + shared `request()` wrapper that unwraps the `{"detail": {"code", "message"}}` error shape into a typed `ApiError`. **Every money/quantity field is typed `string`** in the TS interfaces — there is no `number`-typed money anywhere in the codebase.
- `src/shared/money.ts`:
  - `formatMoney(value: string): string` — presentation only: prefix `£`, thousands separators inserted by string manipulation on the integer part. **No `Number()`, `parseFloat`, or arithmetic.** Server strings are already quantized to 2 dp.
  - `isValidMoneyInput(value: string): boolean` and `isValidQuantityInput(value: string): boolean` — regex validation (`^\d{1,8}(\.\d{1,4})?$` for unit price, 3 dp for quantity). Inputs are `<input type="text" inputMode="decimal">`, never `type="number"` (number inputs are float-shaped).
- Layout: sidebar nav (Invoices, Clients, Settings), content area. Keep styling clean and minimal — Tailwind utilities only, no component library.
- Error handling: `ApiError` surfaces as an inline alert on the page/form that caused it, showing the server's `message`. No toast library.

## Task 2 — Clients

- `/clients`: table (name, city, VAT number, status), "Show archived" toggle (drives `include_archived`), New Client button. Archived rows visually muted with an Unarchive action; active rows have Edit and Archive actions. Archive asks for confirmation.
- `/clients/new`, `/clients/:id/edit`: one form component. No delete anywhere in the UI.

## Task 3 — Settings (company profile)

- `/settings`: single form bound to `GET/PUT /company-profile`. On 404 `company_profile_missing`, render the empty form with a note that the profile must be saved before invoices can be issued.

## Task 4 — Invoices list

- `/invoices`: table (number or "Draft", status badge, client name, invoice date or "—", gross total), status filter tabs (All / Draft / Issued / Void). Gross totals shown **only for issued/void rows, read from the snapshot** (`snapshot.totals.gross` via `formatMoney`); draft rows show "—" — the list makes zero compute calls.
- Row click → editor for drafts, read-only view otherwise. "New Invoice" button.

## Task 5 — Invoice editor (drafts only)

- `/invoices/:id/edit` (and `/invoices/new` which creates the draft on first save):
  - Client select (active clients only), notes, due date.
  - Lines table: description, quantity, unit price, VAT rate select (`standard | reduced | zero | exempt`), remove-line; Add Line button. Position managed automatically by row order.
  - **Live totals panel:** per-rate-group breakdown + net/VAT/gross, fed by `POST /invoices/preview-totals`, debounced 400 ms after the last edit, only when all line inputs pass validation. While a request is in flight or inputs are invalid, the panel shows a subtle "—" state, never stale numbers presented as current. Values rendered via `formatMoney` from the server strings, verbatim.
  - Explicit **Save** (POST for new / PUT for existing, full replace with lines). Unsaved-changes indicator. No autosave.
  - **Issue** button (enabled only after save, i.e. no unsaved changes): opens a confirmation dialog with invoice date (default today), tax point (default = invoice date), due date (prefilled from draft), and the current server totals. Confirm → `POST /invoices/{id}/issue` → navigate to the read-only view. A 409/422 from the server renders its message in the dialog.
  - Delete Draft button with confirmation (drafts only).

## Task 6 — Read-only invoice view (issued / void)

- `/invoices/:id`: renders **exclusively from `snapshot`** — seller block, client block, dates, number, lines table (with per-line rate and net), per-group VAT breakdown, totals. A "VOID" banner for void invoices. Void action (with confirmation) available on issued invoices.
- No edit affordances of any kind. This layout is the dry run for the Phase 4 PDF — keep its structure close to a real UK invoice: seller top-left, invoice meta top-right, lines, VAT breakdown, totals bottom-right, bank details footer.

## Task 7 — Tests

- Unit (vitest): `formatMoney` (thousands separators, no mutation of the decimal part), input validators (rejects `1,5`, `1.12345`, empty, letters; accepts boundary cases).
- Component (testing-library + msw): editor totals flow — type a line, advance the debounce, assert the panel shows exactly the msw-mocked server strings; invalid input → panel shows "—" and no request fires. Issue dialog: 409 from msw renders the server message.
- Grep proofs for the PR description: no `parseFloat`, no `Number(` on money fields, no `toFixed`, no `type="number"` on money/quantity inputs, no arithmetic operators applied to money values in `src/`.
- CI: add `npm run test` (vitest run) to the frontend job.

## Acceptance criteria

- [ ] Full flow works in the browser against the local backend: create client → set up profile → build draft with live totals → save → issue via dialog → read-only snapshot view → void
- [ ] Draft list, editor, and read-only view all render money exclusively from server strings
- [ ] `preview-totals` endpoint tested and OpenAPI-clean; all backend tests still green
- [ ] `npm run lint`, `tsc --noEmit`, `npm run test`, `npm run build` green locally and in CI
- [ ] All grep proofs pass
- [ ] No dependencies beyond those listed in Task 1

## Do NOT

- No PDF work — Phase 4.
- No auth, no pagination, no optimistic updates, no component libraries, no CSS frameworks beyond Tailwind, no state managers beyond React Query + local state.
- No client-side money arithmetic — if a value isn't on the server response, the UI does not show it.
- No autosave.

## Deliverable

Feature branch `phase-3-frontend`, PR to `main` titled "Phase 3: frontend — clients, invoice editor, issue flow", green CI, PR description with deviations and grep proofs.
