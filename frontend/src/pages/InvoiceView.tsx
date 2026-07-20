import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getInvoice, voidInvoice } from '../api/invoices'
import type { InvoiceSnapshot } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorAlert } from '../components/ErrorAlert'
import { formatMoney, formatRate } from '../shared/money'

/**
 * Read-only view of an issued or void invoice.
 *
 * Everything on this page comes from `invoice.snapshot` — the record frozen at
 * issue. Nothing is read from live master data and nothing is recomputed, so
 * archiving the client or changing a VAT rate tomorrow cannot alter what this
 * shows. The layout deliberately follows a real UK invoice (seller top-left,
 * meta top-right, lines, VAT breakdown, totals bottom-right, bank details
 * footer); Phase 4's PDF renders the same structure from the same source.
 */
export function InvoiceView() {
  const { id } = useParams()
  const invoiceId = Number(id)
  const queryClient = useQueryClient()
  const [confirmingVoid, setConfirmingVoid] = useState(false)

  const invoice = useQuery({
    queryKey: ['invoice', invoiceId],
    queryFn: () => getInvoice(invoiceId),
  })

  const voidIt = useMutation({
    mutationFn: () => voidInvoice(invoiceId),
    onSuccess: () => {
      setConfirmingVoid(false)
      void queryClient.invalidateQueries({ queryKey: ['invoice', invoiceId] })
      void queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
  })

  if (invoice.isPending) return <p className="text-sm text-gray-500">Loading…</p>
  if (invoice.error) return <ErrorAlert error={invoice.error} />

  const snapshot = invoice.data?.snapshot
  if (!snapshot) {
    return (
      <div>
        <ErrorAlert error={null} />
        <p className="text-sm text-gray-600">
          This invoice is still a draft.{' '}
          <Link to={`/invoices/${invoiceId}/edit`} className="underline underline-offset-4">
            Open the editor
          </Link>
          .
        </p>
      </div>
    )
  }

  const isVoid = invoice.data.status === 'void'

  return (
    <div className="max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <Link to="/invoices" className="text-sm underline underline-offset-4">
          ← All invoices
        </Link>
        {!isVoid ? (
          <button
            type="button"
            onClick={() => setConfirmingVoid(true)}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50"
          >
            Void invoice
          </button>
        ) : null}
      </div>

      <ErrorAlert error={voidIt.error} />

      {isVoid ? (
        <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-center text-sm font-semibold uppercase tracking-widest text-amber-900">
          Void
        </div>
      ) : null}

      <article className="rounded-lg border border-gray-200 bg-white p-8">
        <header className="flex justify-between gap-8">
          <div className="text-sm leading-relaxed">
            <p className="text-base font-semibold">{snapshot.seller.trading_name}</p>
            <p>{snapshot.seller.address_line1}</p>
            {snapshot.seller.address_line2 ? <p>{snapshot.seller.address_line2}</p> : null}
            <p>{snapshot.seller.city}</p>
            <p>{snapshot.seller.postcode}</p>
            {snapshot.seller.vat_number ? (
              <p className="mt-2">VAT No: {snapshot.seller.vat_number}</p>
            ) : null}
            {snapshot.seller.company_number ? (
              <p>Company No: {snapshot.seller.company_number}</p>
            ) : null}
          </div>

          <div className="text-right text-sm">
            <h2 className="text-2xl font-semibold tracking-tight">Invoice</h2>
            <p className="mt-1 font-medium">{snapshot.number}</p>
            <dl className="mt-4 space-y-1">
              <MetaRow label="Invoice date" value={snapshot.invoice_date} />
              <MetaRow label="Tax point" value={snapshot.tax_point_date} />
              <MetaRow label="Due date" value={snapshot.due_date ?? '—'} />
            </dl>
          </div>
        </header>

        <section className="mt-8 text-sm">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Bill to
          </h3>
          <p className="mt-1 font-medium">{snapshot.client.name}</p>
          <p>{snapshot.client.address_line1}</p>
          {snapshot.client.address_line2 ? <p>{snapshot.client.address_line2}</p> : null}
          <p>{snapshot.client.city}</p>
          <p>{snapshot.client.postcode}</p>
          {snapshot.client.vat_number ? <p className="mt-1">VAT No: {snapshot.client.vat_number}</p> : null}
        </section>

        <table className="mt-8 w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-300 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4 font-medium">Description</th>
              <th className="py-2 pr-4 text-right font-medium">Qty</th>
              <th className="py-2 pr-4 text-right font-medium">Unit price</th>
              <th className="py-2 pr-4 text-right font-medium">VAT</th>
              <th className="py-2 text-right font-medium">Net</th>
            </tr>
          </thead>
          <tbody>
            {snapshot.lines.map((line) => (
              <tr key={line.position} className="border-b border-gray-100">
                <td className="py-2 pr-4">{line.description}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{line.quantity}</td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {formatMoney(line.unit_price)}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">{formatRate(line.rate)}</td>
                <td className="py-2 text-right tabular-nums">{formatMoney(line.line_net)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-8 flex justify-end">
          <div className="w-80 text-sm">
            <VatBreakdown snapshot={snapshot} />
            <dl className="mt-3 space-y-1 border-t border-gray-300 pt-3">
              <TotalRow label="Total excluding VAT" value={snapshot.totals.net} />
              <TotalRow label="Total VAT" value={snapshot.totals.vat} />
              <TotalRow label="Amount due" value={snapshot.totals.gross} emphasis />
            </dl>
          </div>
        </div>

        {snapshot.seller.bank_account_number ? (
          <footer className="mt-10 border-t border-gray-200 pt-4 text-xs text-gray-600">
            <p className="font-medium text-gray-700">Payment details</p>
            <p>
              {snapshot.seller.bank_account_name} · Sort code{' '}
              {snapshot.seller.bank_sort_code} · Account{' '}
              {snapshot.seller.bank_account_number}
            </p>
          </footer>
        ) : null}
      </article>

      {confirmingVoid ? (
        <ConfirmDialog
          title={`Void ${snapshot.number}?`}
          confirmLabel="Void invoice"
          busy={voidIt.isPending}
          onCancel={() => setConfirmingVoid(false)}
          onConfirm={() => voidIt.mutate()}
        >
          <p>
            The invoice stays on record with its number and snapshot intact — a voided
            number is never reused, so the sequence keeps no gaps. This cannot be undone.
          </p>
        </ConfirmDialog>
      ) : null}
    </div>
  )
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-8">
      <dt className="text-gray-500">{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  )
}

function TotalRow({
  label,
  value,
  emphasis = false,
}: {
  label: string
  value: string
  emphasis?: boolean
}) {
  return (
    <div className={`flex justify-between gap-8 ${emphasis ? 'text-base font-semibold' : ''}`}>
      <dt className={emphasis ? '' : 'text-gray-500'}>{label}</dt>
      <dd className="tabular-nums">{formatMoney(value)}</dd>
    </div>
  )
}

function VatBreakdown({ snapshot }: { snapshot: InvoiceSnapshot }) {
  return (
    <dl className="space-y-1">
      {snapshot.groups.map((group) => (
        <div key={group.code} className="flex justify-between gap-8">
          <dt className="capitalize text-gray-500">
            {group.code} ({formatRate(group.rate)}) on {formatMoney(group.net)}
          </dt>
          <dd className="tabular-nums">{formatMoney(group.vat)}</dd>
        </div>
      ))}
    </dl>
  )
}
