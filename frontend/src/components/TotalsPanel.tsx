import type { InvoiceTotals } from '../api/types'
import { formatMoney, formatRate } from '../shared/money'

interface TotalsPanelProps {
  totals: InvoiceTotals | null
  loading?: boolean
  title?: string
}

/**
 * Displays server-computed totals. Every value is a server string rendered
 * verbatim through `formatMoney` — this component does no arithmetic, and when
 * `totals` is null it shows a dash rather than anything it made up or anything
 * left over from a previous state.
 */
export function TotalsPanel({ totals, loading = false, title = 'Totals' }: TotalsPanelProps) {
  const placeholder = <span className="text-gray-400">—</span>

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
        {loading ? <span className="text-xs text-gray-400">Updating…</span> : null}
      </div>

      <dl className="space-y-1">
        {totals
          ? totals.groups.map((group) => (
              <div key={group.code} className="flex justify-between gap-6">
                <dt className="capitalize text-gray-500">
                  {group.code} ({formatRate(group.rate)}) on {formatMoney(group.net)}
                </dt>
                <dd className="tabular-nums">{formatMoney(group.vat)}</dd>
              </div>
            ))
          : null}
      </dl>

      <dl className="mt-3 space-y-1 border-t border-gray-200 pt-3">
        <div className="flex justify-between gap-6">
          <dt className="text-gray-500">Net</dt>
          <dd className="tabular-nums" data-testid="total-net">
            {totals ? formatMoney(totals.total_net) : placeholder}
          </dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt className="text-gray-500">VAT</dt>
          <dd className="tabular-nums" data-testid="total-vat">
            {totals ? formatMoney(totals.total_vat) : placeholder}
          </dd>
        </div>
        <div className="flex justify-between gap-6 text-base font-semibold">
          <dt>Gross</dt>
          <dd className="tabular-nums" data-testid="total-gross">
            {totals ? formatMoney(totals.total_gross) : placeholder}
          </dd>
        </div>
      </dl>
    </div>
  )
}
