# CLAUDE.md — Project Law

These rules are binding for all work in this repository. They exist because they
prevent real bugs. Do not violate them, and do not weaken them without an
explicit prompt instructing you to.

## Money & VAT

1. **Decimal only.** All money is `Decimal` with `ROUND_HALF_UP`. Floats never
   touch money. VAT is rounded **per rate group**, not per line.
2. **Server computes, client displays.** The server computes all money. The
   client only displays server-returned values — it never calculates totals.

## Invoices

3. **Issued invoices are immutable.** On issue, an invoice snapshots the seller,
   client, lines, and rates as they were at issue time. Later edits to master
   data never change an issued invoice.
4. **Gapless numbering, allocated only at issue.** Invoice numbers are gapless
   and allocated only at the moment of issue, inside a transaction. Drafts have
   no number.

## Master data

5. **Archive, never delete.** Master data (clients, items) is archived, never
   hard-deleted, so issued invoices keep valid references.
6. **VAT rates are effective-dated reference data.** UK VAT rates (standard 20%,
   reduced 5%, zero 0%, exempt) are effective-dated reference data — never
   hardcoded in business logic.

## Scope

7. **Out of scope for the PoC** — never build unless a prompt explicitly says so:
   multi-tenancy, HMRC / Making Tax Digital, e-invoicing, multi-currency, credit
   notes. *(Amended in Phase 4: real auth is now in scope — registration, login,
   session cookies, and per-user ownership exist. Still out of scope: email
   verification, password reset, OAuth / social login, and roles/permissions.)*

## Ownership

9. **Every domain query is scoped to its owner.** Each user owns their clients,
   company profile, invoices, and numbering. Every read and write filters by the
   authenticated owner; a resource belonging to another user is **404
   `not_found`, never 403** — existence must not leak across owners. Any new
   domain table gets an `owner_id` (FK to `user`, `ON DELETE RESTRICT`, NOT NULL)
   from birth. `vat_rate` is the sole exception: it is global reference data.

## Workflow

8. Work on feature branches, PR to `main`, and CI must be green before merge.
   Prompts live in `prompts/` and are committed as they are executed.
