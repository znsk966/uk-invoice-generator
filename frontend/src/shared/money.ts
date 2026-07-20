/**
 * Money handling on the client — presentation and validation only.
 *
 * Project law: the server computes money, the client displays it. This file
 * contains **no arithmetic on money whatsoever**: no `Number()`, no
 * `parseFloat`, no `toFixed`, no `+ - * /` applied to a money value. Every
 * amount arrives from the server as a decimal string already quantized to the
 * right number of places, and formatting is pure string manipulation.
 *
 * The reason is not fussiness: `Number("0.1") + Number("0.2")` is
 * `0.30000000000000004`, and once a money value has been through a JS number it
 * is no longer trustworthy. Keeping it a string makes the mistake unavailable.
 */

/** A money string from the server, e.g. `"1425.00"`. */
export function formatMoney(value: string): string {
  const negative = value.startsWith('-')
  const unsigned = negative ? value.slice(1) : value

  const separatorIndex = unsigned.indexOf('.')
  const integerPart = separatorIndex === -1 ? unsigned : unsigned.slice(0, separatorIndex)
  // Kept exactly as the server sent it — never re-rounded, never re-padded.
  const decimalPart = separatorIndex === -1 ? '' : unsigned.slice(separatorIndex)

  return `${negative ? '-' : ''}£${groupThousands(integerPart)}${decimalPart}`
}

/** Insert thousands separators by walking the digits from the right. */
function groupThousands(digits: string): string {
  let grouped = ''
  let count = 0

  for (let index = digits.length - 1; index >= 0; index -= 1) {
    grouped = digits[index] + grouped
    count += 1
    if (count % 3 === 0 && index > 0) {
      grouped = `,${grouped}`
    }
  }

  return grouped
}

/**
 * Render a VAT rate fraction (`"0.2000"`) as a percentage label (`"20%"`).
 *
 * Still no arithmetic: the fraction is shifted two places by moving the decimal
 * point through the string, then trailing zeros are trimmed.
 */
export function formatRate(rate: string): string {
  const [whole, fraction = ''] = rate.split('.')
  const padded = fraction.padEnd(4, '0')
  const shifted = `${whole}${padded.slice(0, 2)}.${padded.slice(2)}`
  const trimmed = shifted.replace(/\.?0+$/, '').replace(/^0+(?=\d)/, '')
  return `${trimmed === '' ? '0' : trimmed}%`
}

/** Up to 8 integer digits and up to 4 decimal places — matches `Numeric(12, 4)`. */
const MONEY_INPUT = /^\d{1,8}(\.\d{1,4})?$/

/** Up to 8 integer digits and up to 3 decimal places — matches `Numeric(12, 3)`. */
const QUANTITY_INPUT = /^\d{1,8}(\.\d{1,3})?$/

/**
 * Is this raw input text a value we are willing to send as a unit price?
 *
 * Rejects the empty string, letters, comma decimal marks (`1,5`), and more
 * precision than the column holds. Inputs are `type="text"
 * inputMode="decimal"`, never `type="number"` — a number input hands back a
 * float-shaped value and accepts things like `1e3`.
 */
export function isValidMoneyInput(value: string): boolean {
  return MONEY_INPUT.test(value)
}

export function isValidQuantityInput(value: string): boolean {
  return QUANTITY_INPUT.test(value)
}
