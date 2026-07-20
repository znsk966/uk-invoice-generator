/**
 * Wire types for the API.
 *
 * Project law: the server computes money, the client displays it. Every money,
 * quantity, and rate field below is typed `string` — deliberately, and without
 * exception. The API sends them as JSON strings (a JSON *number* is a float in
 * every JS parser, and floats must never touch money), and they stay strings
 * all the way to the DOM. There is no `number`-typed money anywhere in this
 * codebase, so there is nothing to accidentally do arithmetic on.
 */

export type VatRateCode = 'standard' | 'reduced' | 'zero' | 'exempt'

export const VAT_RATE_CODES: VatRateCode[] = ['standard', 'reduced', 'zero', 'exempt']

export type InvoiceStatus = 'draft' | 'issued' | 'void'

export interface Client {
  id: number
  name: string
  address_line1: string
  address_line2: string | null
  city: string
  postcode: string
  country: string
  vat_number: string | null
  email: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
}

export type ClientWrite = Omit<
  Client,
  'id' | 'archived_at' | 'created_at' | 'updated_at'
>

export interface CompanyProfile {
  id: number
  trading_name: string
  address_line1: string
  address_line2: string | null
  city: string
  postcode: string
  country: string
  vat_number: string | null
  company_number: string | null
  email: string | null
  phone: string | null
  bank_account_name: string | null
  bank_sort_code: string | null
  bank_account_number: string | null
  created_at: string
  updated_at: string
}

export type CompanyProfileWrite = Omit<CompanyProfile, 'id' | 'created_at' | 'updated_at'>

/** One editable line. `quantity` and `unit_price` are strings — see the note above. */
export interface InvoiceLineInput {
  position: number
  description: string
  quantity: string
  unit_price: string
  vat_rate_code: VatRateCode
}

export interface InvoiceLine extends InvoiceLineInput {
  id: number
}

export interface RateGroup {
  code: VatRateCode
  rate: string
  net: string
  vat: string
  gross: string
}

export interface InvoiceTotals {
  groups: RateGroup[]
  total_net: string
  total_vat: string
  total_gross: string
}

/** A line as frozen into the snapshot at issue: inputs plus what was computed. */
export interface SnapshotLine extends InvoiceLineInput {
  rate: string
  line_net: string
}

/**
 * The immutable record written at issue. Everything an issued invoice displays
 * comes from here — never from live master data, never recomputed.
 */
export interface InvoiceSnapshot {
  version: number
  number: string
  invoice_date: string
  tax_point_date: string
  due_date: string | null
  currency: string
  seller: Omit<CompanyProfile, 'id' | 'created_at' | 'updated_at'>
  client: Omit<Client, 'id' | 'archived_at' | 'created_at' | 'updated_at'>
  lines: SnapshotLine[]
  groups: RateGroup[]
  totals: { net: string; vat: string; gross: string }
}

export interface Invoice {
  id: number
  status: InvoiceStatus
  number: string | null
  client_id: number
  invoice_date: string | null
  tax_point_date: string | null
  due_date: string | null
  currency: string
  notes: string | null
  lines: InvoiceLine[]
  snapshot: InvoiceSnapshot | null
  issued_at: string | null
  created_at: string
  updated_at: string
}

export interface InvoiceWrite {
  client_id: number
  notes: string | null
  due_date: string | null
  lines: InvoiceLineInput[]
}

export interface IssueRequest {
  invoice_date?: string | null
  tax_point_date?: string | null
  due_date?: string | null
}

export interface PreviewTotalsRequest {
  lines: InvoiceLineInput[]
  on_date?: string | null
}
