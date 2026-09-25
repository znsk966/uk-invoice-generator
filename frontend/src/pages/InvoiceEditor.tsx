import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { listClients } from '../api/clients'
import {
  createInvoice,
  deleteInvoice,
  getInvoice,
  getInvoiceTotals,
  issueInvoice,
  updateInvoice,
} from '../api/invoices'
import type { InvoiceLineInput, InvoiceWrite, VatRateCode } from '../api/types'
import { VAT_RATE_CODES } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorAlert } from '../components/ErrorAlert'
import { Field } from '../components/Field'
import { TotalsPanel } from '../components/TotalsPanel'
import { isValidMoneyInput, isValidQuantityInput } from '../shared/money'
import { useLiveTotals } from '../shared/useLiveTotals'

const BLANK_LINE: Omit<InvoiceLineInput, 'position'> = {
  description: '',
  quantity: '1.000',
  unit_price: '0.0000',
  vat_rate_code: 'standard',
}

interface DraftState {
  clientId: number | null
  notes: string
  dueDate: string
  lines: Omit<InvoiceLineInput, 'position'>[]
}

const EMPTY: DraftState = { clientId: null, notes: '', dueDate: '', lines: [{ ...BLANK_LINE }] }

/** Drafts only. Issued and void invoices open in the read-only view. */
export function InvoiceEditor() {
  const { id } = useParams()
  const invoiceId = id ? Number(id) : null
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [draft, setDraft] = useState<DraftState>(EMPTY)
  const [dirty, setDirty] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [issuing, setIssuing] = useState(false)

  const clients = useQuery({ queryKey: ['clients', false], queryFn: () => listClients(false) })

  const existing = useQuery({
    queryKey: ['invoice', invoiceId],
    queryFn: () => getInvoice(invoiceId as number),
    enabled: invoiceId !== null,
  })

  useEffect(() => {
    if (!existing.data) return
    setDraft({
      clientId: existing.data.client_id,
      notes: existing.data.notes ?? '',
      dueDate: existing.data.due_date ?? '',
      lines: existing.data.lines.map(({ description, quantity, unit_price, vat_rate_code }) => ({
        description,
        quantity,
        unit_price,
        vat_rate_code,
      })),
    })
    setDirty(false)
  }, [existing.data])

  // Positions come from row order, so reordering or removing rows cannot leave
  // a gap or a duplicate for the server to reject.
  const lines: InvoiceLineInput[] = useMemo(
    () => draft.lines.map((line, index) => ({ ...line, position: index + 1 })),
    [draft.lines],
  )

  const linesValid = lines.every(
    (line) =>
      line.description.trim() !== '' &&
      isValidQuantityInput(line.quantity) &&
      isValidMoneyInput(line.unit_price),
  )

  const live = useLiveTotals(lines, linesValid)

  const update = (change: Partial<DraftState>) => {
    setDraft((current) => ({ ...current, ...change }))
    setDirty(true)
  }

  const updateLine = (index: number, change: Partial<Omit<InvoiceLineInput, 'position'>>) =>
    update({
      lines: draft.lines.map((line, at) => (at === index ? { ...line, ...change } : line)),
    })

  const save = useMutation({
    mutationFn: (payload: InvoiceWrite) =>
      invoiceId === null ? createInvoice(payload) : updateInvoice(invoiceId, payload),
    onSuccess: (invoice) => {
      setDirty(false)
      void queryClient.invalidateQueries({ queryKey: ['invoices'] })
      void queryClient.invalidateQueries({ queryKey: ['invoice', invoice.id] })
      if (invoiceId === null) navigate(`/invoices/${invoice.id}/edit`, { replace: true })
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteInvoice(invoiceId as number),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['invoices'] })
      navigate('/invoices')
    },
  })

  const submit = () => {
    if (draft.clientId === null) return
    save.mutate({
      client_id: draft.clientId,
      notes: draft.notes === '' ? null : draft.notes,
      due_date: draft.dueDate === '' ? null : draft.dueDate,
      lines,
    })
  }

  if (invoiceId !== null && existing.data && existing.data.status !== 'draft') {
    navigate(`/invoices/${invoiceId}`, { replace: true })
    return null
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight">
          {invoiceId === null ? 'New invoice' : 'Edit draft'}
        </h2>
        {dirty ? (
          <span className="text-sm text-amber-700">Unsaved changes</span>
        ) : (
          <span className="text-sm text-gray-400">Saved</span>
        )}
      </div>

      <ErrorAlert error={save.error ?? existing.error ?? remove.error ?? live.error} />

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <div className="grid grid-cols-2 gap-4">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-gray-700">
                Client<span className="text-red-600"> *</span>
              </span>
              <select
                value={draft.clientId ?? ''}
                onChange={(event) => update({ clientId: Number(event.target.value) })}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="" disabled>
                  Select a client…
                </option>
                {clients.data?.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.name}
                  </option>
                ))}
              </select>
            </label>

            <Field
              label="Due date"
              type="date"
              value={draft.dueDate}
              onChange={(value) => update({ dueDate: value })}
            />

            <div className="col-span-2">
              <Field
                label="Notes"
                value={draft.notes}
                onChange={(value) => update({ notes: value })}
              />
            </div>
          </div>

          <table className="mt-6 w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2 pr-3 font-medium">Description</th>
                <th className="w-24 py-2 pr-3 font-medium">Qty</th>
                <th className="w-32 py-2 pr-3 font-medium">Unit price</th>
                <th className="w-32 py-2 pr-3 font-medium">VAT</th>
                <th className="w-8 py-2" />
              </tr>
            </thead>
            <tbody>
              {draft.lines.map((line, index) => (
                <tr key={index} className="border-b border-gray-100 align-top">
                  <td className="py-2 pr-3">
                    <input
                      type="text"
                      aria-label={`Description ${index + 1}`}
                      value={line.description}
                      onChange={(event) => updateLine(index, { description: event.target.value })}
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5"
                    />
                  </td>
                  <td className="py-2 pr-3">
                    {/* type="text" + inputMode, never type="number": a number
                        input hands back a float-shaped value. */}
                    <input
                      type="text"
                      inputMode="decimal"
                      aria-label={`Quantity ${index + 1}`}
                      value={line.quantity}
                      onChange={(event) => updateLine(index, { quantity: event.target.value })}
                      className={`w-full rounded-md border px-2 py-1.5 text-right tabular-nums ${
                        isValidQuantityInput(line.quantity)
                          ? 'border-gray-300'
                          : 'border-red-400 bg-red-50'
                      }`}
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <input
                      type="text"
                      inputMode="decimal"
                      aria-label={`Unit price ${index + 1}`}
                      value={line.unit_price}
                      onChange={(event) => updateLine(index, { unit_price: event.target.value })}
                      className={`w-full rounded-md border px-2 py-1.5 text-right tabular-nums ${
                        isValidMoneyInput(line.unit_price)
                          ? 'border-gray-300'
                          : 'border-red-400 bg-red-50'
                      }`}
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <select
                      aria-label={`VAT rate ${index + 1}`}
                      value={line.vat_rate_code}
                      onChange={(event) =>
                        updateLine(index, { vat_rate_code: event.target.value as VatRateCode })
                      }
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5 capitalize"
                    >
                      {VAT_RATE_CODES.map((code) => (
                        <option key={code} value={code}>
                          {code}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2 text-right">
                    {draft.lines.length > 1 ? (
                      <button
                        type="button"
                        aria-label={`Remove line ${index + 1}`}
                        onClick={() =>
                          update({ lines: draft.lines.filter((_, at) => at !== index) })
                        }
                        className="text-gray-400 hover:text-gray-700"
                      >
                        ×
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <button
            type="button"
            onClick={() => update({ lines: [...draft.lines, { ...BLANK_LINE }] })}
            className="mt-3 rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
          >
            Add line
          </button>

          <div className="mt-8 flex gap-2">
            <button
              type="button"
              onClick={submit}
              disabled={save.isPending || draft.clientId === null || !linesValid}
              className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {save.isPending ? 'Saving…' : 'Save'}
            </button>

            {/* Issue works from what is *saved*, so it stays disabled while
                there are unsaved edits — issuing what is on screen but not in
                the database would be the worst possible surprise. */}
            <button
              type="button"
              onClick={() => setIssuing(true)}
              disabled={invoiceId === null || dirty}
              title={dirty ? 'Save your changes before issuing' : undefined}
              className="rounded-md border border-gray-900 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-40"
            >
              Issue…
            </button>

            {invoiceId !== null ? (
              <button
                type="button"
                onClick={() => setConfirmingDelete(true)}
                className="ml-auto rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                Delete draft
              </button>
            ) : null}
          </div>
        </div>

        <div className="col-span-1">
          <TotalsPanel totals={live.totals} loading={live.loading} title="Live totals" />
          {!linesValid ? (
            <p className="mt-2 text-xs text-gray-500">
              Totals appear once every line is valid.
            </p>
          ) : null}
        </div>
      </div>

      {confirmingDelete ? (
        <ConfirmDialog
          title="Delete this draft?"
          confirmLabel="Delete draft"
          busy={remove.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => remove.mutate()}
        >
          <p>Drafts are the one thing that can be deleted outright. This cannot be undone.</p>
        </ConfirmDialog>
      ) : null}

      {issuing && invoiceId !== null ? (
        <IssueDialog
          invoiceId={invoiceId}
          defaultDueDate={draft.dueDate}
          onCancel={() => setIssuing(false)}
          onIssued={() => {
            setIssuing(false)
            void queryClient.invalidateQueries({ queryKey: ['invoices'] })
            navigate(`/invoices/${invoiceId}`)
          }}
        />
      ) : null}
    </div>
  )
}

/** Today in the user's own timezone — `toISOString` would be UTC, which is the
 *  wrong day for anyone invoicing late in the evening west of Greenwich. */
function today(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

interface IssueDialogProps {
  invoiceId: number
  defaultDueDate: string
  onCancel: () => void
  onIssued: () => void
}

/**
 * Issue confirmation. Shows the totals the *server* currently holds for the
 * saved draft, so what is confirmed is what will be frozen into the snapshot.
 */
function IssueDialog({ invoiceId, defaultDueDate, onCancel, onIssued }: IssueDialogProps) {
  const [invoiceDate, setInvoiceDate] = useState(today())
  const [taxPointDate, setTaxPointDate] = useState(today())
  const [dueDate, setDueDate] = useState(defaultDueDate)

  const totals = useQuery({
    queryKey: ['invoice-totals', invoiceId],
    queryFn: () => getInvoiceTotals(invoiceId),
  })

  const issue = useMutation({
    mutationFn: () =>
      issueInvoice(invoiceId, {
        invoice_date: invoiceDate,
        tax_point_date: taxPointDate,
        due_date: dueDate === '' ? null : dueDate,
      }),
    onSuccess: onIssued,
  })

  return (
    <ConfirmDialog
      title="Issue this invoice?"
      confirmLabel="Issue invoice"
      busy={issue.isPending}
      onCancel={onCancel}
      onConfirm={() => issue.mutate()}
    >
      <ErrorAlert error={issue.error} />

      <p className="mb-4">
        Issuing allocates the next invoice number and freezes the seller, client, lines,
        and VAT rates. It cannot be edited afterwards.
      </p>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Invoice date" type="date" value={invoiceDate} onChange={setInvoiceDate} />
        <Field label="Tax point" type="date" value={taxPointDate} onChange={setTaxPointDate} />
        <div className="col-span-2">
          <Field label="Due date" type="date" value={dueDate} onChange={setDueDate} />
        </div>
      </div>

      <div className="mt-4">
        <TotalsPanel totals={totals.data ?? null} loading={totals.isPending} />
      </div>
    </ConfirmDialog>
  )
}
