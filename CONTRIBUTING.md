# Contributing

Thanks for your interest in **uk-invoice-generator**.

- **Issues welcome.** Bug reports, questions, and ideas are all appreciated —
  open an issue.
- **PRs need green CI.** All pull requests target `main` and must pass CI
  (backend lint + tests, frontend lint + typecheck + build) before they can be
  merged.
- **Money-related code requires tests.** Any change touching money, VAT, or
  invoice numbering must come with tests covering the relevant edge cases. See
  the Project Law in [`CLAUDE.md`](CLAUDE.md) — money is `Decimal` with
  `ROUND_HALF_UP`, computed on the server, and this is reviewed line by line.

This is a proof of concept built through a prompt-driven workflow; the prompts
that produced each change live in [`prompts/`](prompts/).
