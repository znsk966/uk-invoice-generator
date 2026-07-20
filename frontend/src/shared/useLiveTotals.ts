import { useEffect, useState } from 'react'

import { previewTotals } from '../api/invoices'
import type { InvoiceLineInput, InvoiceTotals } from '../api/types'

const DEBOUNCE_MS = 400

export interface LiveTotals {
  /** Server-computed totals, or `null` whenever we cannot honestly show any. */
  totals: InvoiceTotals | null
  loading: boolean
  error: unknown
}

/**
 * Live totals for unsaved editor state.
 *
 * Two rules drive the shape of this hook:
 *
 * 1. **The server computes; we display.** Totals only ever come from
 *    `POST /invoices/preview-totals`. Nothing here adds anything up.
 * 2. **Never show stale numbers as current.** The moment the lines change, the
 *    previous totals are dropped and the panel falls back to a "—" state. Old
 *    numbers sitting under new inputs would be a lie, and a convincing one.
 *
 * Requests are debounced 400 ms after the last edit and only fire when every
 * line passes validation; an in-flight request is aborted if the lines change
 * again, so a slow response can never overwrite a newer one.
 */
export function useLiveTotals(lines: InvoiceLineInput[], valid: boolean): LiveTotals {
  const [totals, setTotals] = useState<InvoiceTotals | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)

  // Serialising the lines gives a stable dependency: the effect re-runs when
  // the *content* changes, not on every re-render.
  const key = JSON.stringify(lines)

  useEffect(() => {
    // Rule 2: whatever we were showing is now out of date.
    setTotals(null)
    setError(null)

    if (!valid || lines.length === 0) {
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)

    const timer = setTimeout(() => {
      previewTotals({ lines }, controller.signal)
        .then((result) => {
          setTotals(result)
          setLoading(false)
        })
        .catch((cause: unknown) => {
          if (controller.signal.aborted) return
          setError(cause)
          setLoading(false)
        })
    }, DEBOUNCE_MS)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
    // `key` stands in for `lines`; see the comment above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, valid])

  return { totals, loading, error }
}
