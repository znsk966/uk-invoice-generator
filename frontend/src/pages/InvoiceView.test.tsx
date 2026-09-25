import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { InvoiceView } from './InvoiceView'

const SELLER = {
  trading_name: 'My Freelance Co',
  address_line1: '2 Baker Street',
  address_line2: null,
  city: 'London',
  postcode: 'NW1 6XE',
  country: 'GB',
  vat_number: 'GB123456789',
  company_number: null,
  email: null,
  phone: null,
  bank_account_name: null,
  bank_sort_code: null,
  bank_account_number: null,
}
const BUYER = {
  name: 'Harbour Analytics Ltd',
  address_line1: '4 Dock Road',
  address_line2: null,
  city: 'Bristol',
  postcode: 'BS1 6EG',
  country: 'GB',
  vat_number: null,
  email: null,
}

/** A v1 snapshot exactly as Phase 2–4 stored it: no product fields anywhere. */
const SNAPSHOT_V1 = {
  version: 1,
  number: 'INV-2026-00001',
  invoice_date: '2026-09-01',
  tax_point_date: '2026-09-01',
  due_date: null,
  currency: 'GBP',
  seller: SELLER,
  client: BUYER,
  lines: [
    {
      position: 1,
      description: 'Consulting',
      quantity: '2.000',
      unit_price: '10.0000',
      vat_rate_code: 'standard',
      rate: '0.2000',
      line_net: '20.00',
    },
  ],
  groups: [{ code: 'standard', rate: '0.2000', net: '20.00', vat: '4.00', gross: '24.00' }],
  totals: { net: '20.00', vat: '4.00', gross: '24.00' },
}

/** A v2 snapshot: one catalog line, one ad-hoc line (product fields null). */
const SNAPSHOT_V2 = {
  ...SNAPSHOT_V1,
  version: 2,
  number: 'INV-2026-00002',
  lines: [
    {
      position: 1,
      description: 'Printed handbook',
      quantity: '1.000',
      unit_price: '25.0000',
      vat_rate_code: 'zero',
      rate: '0.0000',
      line_net: '25.00',
      product_id: 3,
      product_code: 'BOOK',
      kind: 'goods',
    },
    {
      position: 2,
      description: 'Travel',
      quantity: '1.000',
      unit_price: '5.0000',
      vat_rate_code: 'exempt',
      rate: '0.0000',
      line_net: '5.00',
      product_id: null,
      product_code: null,
      kind: null,
    },
  ],
  groups: [
    { code: 'zero', rate: '0.0000', net: '25.00', vat: '0.00', gross: '25.00' },
    { code: 'exempt', rate: '0.0000', net: '5.00', vat: '0.00', gross: '5.00' },
  ],
  totals: { net: '30.00', vat: '0.00', gross: '30.00' },
}

function issued(id: number, snapshot: unknown) {
  return {
    id,
    status: 'issued',
    number: (snapshot as { number: string }).number,
    client_id: 1,
    invoice_date: '2026-09-01',
    tax_point_date: '2026-09-01',
    due_date: null,
    currency: 'GBP',
    notes: null,
    lines: [],
    snapshot,
    issued_at: '2026-09-01T10:00:00Z',
    created_at: '2026-09-01T09:00:00Z',
    updated_at: '2026-09-01T10:00:00Z',
  }
}

const server = setupServer(
  http.get('/api/v1/invoices/1', () => HttpResponse.json(issued(1, SNAPSHOT_V1))),
  http.get('/api/v1/invoices/2', () => HttpResponse.json(issued(2, SNAPSHOT_V2))),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

function renderView(id: number) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/invoices/${id}`]}>
        <Routes>
          <Route path="/invoices/:id" element={<InvoiceView />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('read-only invoice view', () => {
  it('renders a v1 snapshot (no product fields) without errors', async () => {
    renderView(1)
    expect(await screen.findByText('INV-2026-00001')).toBeTruthy()
    expect(screen.getByText('Consulting')).toBeTruthy()
    expect(screen.getByText('£24.00')).toBeTruthy()
    expect(screen.queryByTestId(/^product-code-/)).toBeNull()
  })

  it('renders a v2 snapshot with the product code on the catalog line only', async () => {
    renderView(2)
    expect(await screen.findByText('INV-2026-00002')).toBeTruthy()
    expect(screen.getByText('Printed handbook')).toBeTruthy()
    expect(screen.getByTestId('product-code-1').textContent).toBe('BOOK')
    expect(screen.getByText('Travel')).toBeTruthy()
    expect(screen.queryByTestId('product-code-2')).toBeNull()
    // Net and amount due (zero-rated + exempt, so both are £30.00).
    expect(screen.getAllByText('£30.00')).toHaveLength(2)
  })
})
