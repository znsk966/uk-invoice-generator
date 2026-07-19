# Money & VAT

The rules in this document are not style preferences. They are in
[`CLAUDE.md`](../CLAUDE.md) as project law, they are enforced in three places in
the code, and money-related changes are reviewed line by line.

## Decimal only, `ROUND_HALF_UP`, never float

All money is `decimal.Decimal`, quantized with `ROUND_HALF_UP`. Floats never
touch money — not as input, not as an intermediate, not "just for display".

Binary floating point cannot represent decimal cents exactly. The textbook case:
`2.675` stored as a double is really `2.67499999999999982…`, so rounding it to
two places gives `2.67`, not the `2.68` an accountant expects. A penny lost this
way is invisible in code review and unmissable on an invoice.

`round_money` is the only rounding function:

```python
TWO_PLACES = Decimal("0.01")

def round_money(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(...)     # a float fails loudly; it is never coerced
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
```

### Three enforcement layers

The ban is not a convention anyone has to remember. It is checked at three
independent boundaries, so a float has to defeat all three to reach a total:

1. **The primitives** (`app/core/money.py`). `round_money` accepts only
   `Decimal`. `as_decimal` builds a `Decimal` from `str`, `int`, or `Decimal`
   and raises `TypeError` on `float` — constructing `Decimal(0.1)` would import
   the float's error rather than reject it. `bool` is rejected too, since it is
   an `int` subclass and would otherwise slip through.

2. **The model boundary** (`@validates` hooks). `reject_float` is wired to
   `InvoiceLine.quantity`, `InvoiceLine.unit_price`, and `VatRate.rate`:

   ```python
   @validates("quantity", "unit_price")
   def _reject_float(self, key: str, value: object) -> object:
       return reject_float(key, value)
   ```

   This layer exists because of a real review finding: without it,
   `InvoiceLine(unit_price=0.1)` was silently accepted. The float never reached
   `round_money` — SQLAlchemy coerced it to `Numeric` on the way to the database
   first — so layer 1 never got the chance to complain. Layer 2 is what closes
   that gap, and `tests/unit/test_model_validators.py` holds it open.

3. **The wire format.** Money crosses JSON as a **string**, never a JSON number,
   in both directions. Responses serialize `Decimal` to strings (`"1425.00"`),
   and every money value inside a stored snapshot is a string — asserted at the
   database level with `jsonb_typeof(...) = 'string'`. A JSON number *is* a
   float in most parsers; a string cannot be misread.

   Incoming JSON numbers are still safe: Pydantic v2 parses a JSON number into
   `Decimal` from the **source text**, so `10.10` arrives as exactly
   `Decimal("10.10")`, not `10.0999…`. Money fields also set
   `allow_inf_nan=False`, rejecting `Infinity` and `NaN` — valid IEEE floats,
   meaningless as money.

## Rounding order: line net first, then VAT once per group

The order is fixed and it is not interchangeable:

1. **Per line**: `line_net = round_money(quantity × unit_price)` — 2 dp.
2. **Per rate group**: sum the line nets, then `vat = round_money(group_net × rate)`.
   VAT is rounded **once**, on the group net.
3. `gross = net + vat` per group; the invoice totals are the sums of the group values.

Rounding VAT per line and summing gives a different — wrong — answer. From
`tests/unit/test_vat.py`, nine lines of £0.03 at the 20% standard rate:

| | Arithmetic | VAT |
| --- | --- | --- |
| Per line (**wrong**) | `round(0.03 × 0.20)` = `round(0.006)` = `0.01`, nine times | **0.09** |
| Per group (**correct**) | net = `9 × 0.03` = `0.27`; `round(0.27 × 0.20)` = `round(0.054)` | **0.05** |

Four pence apart on an invoice worth 27p. Scale that to a few hundred small
lines and the invoice disagrees with the VAT return. The engine must produce
`0.05`; the test asserts it, and asserts the per-line figure would have been
`0.09`, so the divergence is documented rather than merely avoided.

Groups always appear in the same order — **standard → reduced → zero → exempt** —
and only groups that actually have lines are emitted. `zero` and `exempt` both
carry a 0% rate but are legally distinct treatments and must be shown as
separate groups on an invoice, so they stay separate codes throughout.

## Numeric precision

| Value | Type | Why |
| --- | --- | --- |
| Money (nets, VAT, gross) | `Numeric(12, 2)` | Pence. This is the currency's own precision; there is nothing finer to keep. |
| Unit price | `Numeric(12, 4)` | Per-unit prices legitimately carry sub-penny precision (£0.0325 per unit). Rounding to money happens once, at the line, after multiplying. |
| Quantity | `Numeric(12, 3)` | Hours, kilos, and part-units, without inviting float-shaped precision. |
| VAT rate | `Numeric(5, 4)` | Stored as a fraction: 20% is `0.2000`. Four places covers rates like 12.5% exactly. |

`12` digits of total precision allows amounts up to 9,999,999,999.99 — far past
anything a PoC invoice needs, and it costs nothing.

Every column spells out `asdecimal=True` and is annotated `Mapped[Decimal]`,
even though `asdecimal=True` is already the psycopg default. Explicit beats
implicit on money columns: it documents intent for a contributor who has not
read this file, and the annotation makes a type checker enforce the Python side
too.

## VAT rates are effective-dated reference data

Rates are rows in `vat_rate`, never constants in business logic. Each row is one
code over a half-open date range: `valid_from` inclusive, `valid_to` inclusive
or `NULL` for "still current". `(code, valid_from)` is unique.

The seed migration loads the current UK rates, effective **2011-01-04** (the day
the standard rate rose to 20%), all open-ended:

| Code | Rate | Meaning |
| --- | --- | --- |
| `standard` | `0.2000` | 20% |
| `reduced` | `0.0500` | 5% |
| `zero` | `0.0000` | Zero-rated (taxable at 0%) |
| `exempt` | `0.0000` | Exempt from VAT (not a taxable supply) |

`rates_on(session, on_date)` returns the applicable fraction for **every** code
on that date, and raises `LookupError` if any of the four is missing. It does
not fall back to a default — an invoice must never be issued with a silently
assumed rate.

### Rates are taken at the tax point

`issue_invoice` resolves rates with `rates_on(session, tax_point_date)`, not
"today". The tax point defaults to the invoice date, which defaults to today,
but when it is supplied it governs: an invoice issued today for a supply whose
tax point was in a different rate regime gets that regime's rates.

A tax point with no applicable rate surfaces as `422 validation_failed` rather
than a fallback. Against the seeded data, a tax point before 2011-01-04 is
exactly that case, and there is a test for it.

Because the resolved rate is written into the snapshot at issue, a later rate
change — a new `vat_rate` row — cannot alter what an already-issued invoice
says. See [INVOICING.md](INVOICING.md#the-snapshot).
