import { describe, expect, it } from 'vitest'

import { formatMoney, formatRate, isValidMoneyInput, isValidQuantityInput } from './money'

describe('formatMoney', () => {
  it('prefixes the currency and keeps the decimal part exactly as sent', () => {
    expect(formatMoney('20.00')).toBe('£20.00')
    expect(formatMoney('0.05')).toBe('£0.05')
  })

  it('inserts thousands separators', () => {
    expect(formatMoney('1425.00')).toBe('£1,425.00')
    expect(formatMoney('999.99')).toBe('£999.99')
    expect(formatMoney('1000.00')).toBe('£1,000.00')
    expect(formatMoney('1234567.89')).toBe('£1,234,567.89')
  })

  it('never touches the decimal part — no re-rounding, no re-padding', () => {
    // A 4 dp unit price stays 4 dp; formatting is not a place to change precision.
    expect(formatMoney('10.1000')).toBe('£10.1000')
    expect(formatMoney('0.0325')).toBe('£0.0325')
    // Trailing zeros the server chose to send are meaningful and are preserved.
    expect(formatMoney('1200.50')).toBe('£1,200.50')
  })

  it('handles values with no decimal part', () => {
    expect(formatMoney('42')).toBe('£42')
    expect(formatMoney('1000')).toBe('£1,000')
  })

  it('keeps a negative sign outside the currency symbol', () => {
    expect(formatMoney('-1234.56')).toBe('-£1,234.56')
  })

  it('is a pure string transform — huge values survive intact', () => {
    // Beyond Number.MAX_SAFE_INTEGER: proof that nothing here goes via a float.
    expect(formatMoney('9007199254740993.01')).toBe('£9,007,199,254,740,993.01')
  })
})

describe('formatRate', () => {
  it('renders rate fractions as percentages', () => {
    expect(formatRate('0.2000')).toBe('20%')
    expect(formatRate('0.0500')).toBe('5%')
    expect(formatRate('0.0000')).toBe('0%')
    expect(formatRate('0.1250')).toBe('12.5%')
  })
})

describe('isValidMoneyInput', () => {
  it('accepts plain decimals up to 4 places', () => {
    expect(isValidMoneyInput('0')).toBe(true)
    expect(isValidMoneyInput('10')).toBe(true)
    expect(isValidMoneyInput('10.5')).toBe(true)
    expect(isValidMoneyInput('650.0000')).toBe(true)
    expect(isValidMoneyInput('99999999.9999')).toBe(true)
  })

  it('rejects anything that is not a plain decimal', () => {
    expect(isValidMoneyInput('')).toBe(false)
    expect(isValidMoneyInput('1,5')).toBe(false) // comma decimal mark
    expect(isValidMoneyInput('1.12345')).toBe(false) // more precision than the column holds
    expect(isValidMoneyInput('abc')).toBe(false)
    expect(isValidMoneyInput('10.')).toBe(false)
    expect(isValidMoneyInput('.5')).toBe(false)
    expect(isValidMoneyInput('-1.00')).toBe(false)
    expect(isValidMoneyInput('1e3')).toBe(false) // what type="number" would allow
    expect(isValidMoneyInput(' 1.00')).toBe(false)
    expect(isValidMoneyInput('999999999')).toBe(false) // 9 integer digits
  })
})

describe('isValidQuantityInput', () => {
  it('accepts up to 3 decimal places', () => {
    expect(isValidQuantityInput('1')).toBe(true)
    expect(isValidQuantityInput('2.000')).toBe(true)
    expect(isValidQuantityInput('0.125')).toBe(true)
  })

  it('rejects a 4th decimal place', () => {
    expect(isValidQuantityInput('1.0000')).toBe(false)
    expect(isValidQuantityInput('')).toBe(false)
    expect(isValidQuantityInput('1,5')).toBe(false)
  })
})
