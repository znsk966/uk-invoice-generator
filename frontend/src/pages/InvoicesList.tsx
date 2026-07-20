import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { listClients } from '../api/clients'
import { listInvoices } from '../api/invoices'
import type { Invoice, InvoiceStatus } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { StatusBadge } from '../components/StatusBadge'
import { formatMoney } from '../shared/money'

const TABS: { label: string; status?: InvoiceStatus }[] = [
  { label: 'All' },
  { label: 'Draft', status: 'draft' },
  { label: 'Issued', status: 'issued' },
  { label: 'Void', status: 'void' },
]

export function InvoicesList() {
  const [status, setStatus] = useState<InvoiceStatus | undefined>(undefined)
  const navigate = useNavigate()

  const invoices = useQuery({
    queryKey: ['invoices', status],
    queryFn: () => listInvoices(status),
  })

  // Only to label rows; no money comes from here.
  const clients = useQuery({ queryKey: ['clients', true], queryFn: () => listClients(true) })
  const clientName = (id: number) =>
    clients.data?.find((client) => client.id === id)?.name ?? '—'

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight">Invoices</h2>
        <Link
          to="/invoices/new"
          className="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          New Invoice
        </Link>
      </div>

      <ErrorAlert error={invoices.error} />

      <div className="mb-4 flex gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.label}
            type="button"
            onClick={() => setStatus(tab.status)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              status === tab.status
                ? 'bg-gray-900 font-medium text-white'
                : 'text-gray-700 hover:bg-gray-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {invoices.isPending ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : invoices.data && invoices.data.length > 0 ? (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4 font-medium">Number</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 pr-4 font-medium">Client</th>
              <th className="py-2 pr-4 font-medium">Invoice date</th>
              <th className="py-2 text-right font-medium">Gross</th>
            </tr>
          </thead>
          <tbody>
            {invoices.data.map((invoice) => (
              <tr
                key={invoice.id}
                onClick={() => navigate(destinationFor(invoice))}
                className="cursor-pointer border-b border-gray-100 hover:bg-gray-50"
              >
                <td className="py-2 pr-4 font-medium">{invoice.number ?? 'Draft'}</td>
                <td className="py-2 pr-4">
                  <StatusBadge status={invoice.status} />
                </td>
                <td className="py-2 pr-4">{clientName(invoice.client_id)}</td>
                <td className="py-2 pr-4">{invoice.invoice_date ?? '—'}</td>
                <td className="py-2 text-right tabular-nums">
                  {/*
                    Gross is shown only for issued/void rows, straight from the
                    snapshot. Drafts show a dash: the list never asks the server
                    to compute anything, and it certainly never computes itself.
                  */}
                  {invoice.snapshot ? formatMoney(invoice.snapshot.totals.gross) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-gray-500">No invoices yet.</p>
      )}
    </div>
  )
}

function destinationFor(invoice: Invoice): string {
  return invoice.status === 'draft' ? `/invoices/${invoice.id}/edit` : `/invoices/${invoice.id}`
}
