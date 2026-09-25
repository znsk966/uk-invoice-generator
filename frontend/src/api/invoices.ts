import { request } from './client'
import type {
  Invoice,
  InvoiceStatus,
  InvoiceTotals,
  InvoiceWrite,
  IssueRequest,
  PreviewTotalsRequest,
} from './types'

export function listInvoices(status?: InvoiceStatus): Promise<Invoice[]> {
  return request<Invoice[]>(status ? `/invoices?status=${status}` : '/invoices')
}

export function getInvoice(id: number): Promise<Invoice> {
  return request<Invoice>(`/invoices/${id}`)
}

export function createInvoice(payload: InvoiceWrite): Promise<Invoice> {
  return request<Invoice>('/invoices', { method: 'POST', body: payload })
}

export function updateInvoice(id: number, payload: InvoiceWrite): Promise<Invoice> {
  return request<Invoice>(`/invoices/${id}`, { method: 'PUT', body: payload })
}

export function deleteInvoice(id: number): Promise<void> {
  return request<void>(`/invoices/${id}`, { method: 'DELETE' })
}

/**
 * Totals for a saved invoice. Computed live for drafts; for issued/void the
 * server returns the snapshot values verbatim.
 */
export function getInvoiceTotals(id: number): Promise<InvoiceTotals> {
  return request<InvoiceTotals>(`/invoices/${id}/totals`)
}

/**
 * Totals for *unsaved* editor state. Stateless — the server does the arithmetic
 * so the client never has to, without autosaving a draft on every keystroke.
 */
export function previewTotals(
  payload: PreviewTotalsRequest,
  signal?: AbortSignal,
): Promise<InvoiceTotals> {
  return request<InvoiceTotals>('/invoices/preview-totals', {
    method: 'POST',
    body: payload,
    signal,
  })
}

export function issueInvoice(id: number, payload: IssueRequest = {}): Promise<Invoice> {
  return request<Invoice>(`/invoices/${id}/issue`, { method: 'POST', body: payload })
}

export function voidInvoice(id: number): Promise<Invoice> {
  return request<Invoice>(`/invoices/${id}/void`, { method: 'POST' })
}
