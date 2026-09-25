import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'

import { InvoiceEditor } from './InvoiceEditor'

const CLIENT = {
  id: 1,
  name: 'Harbour Analytics Ltd',
  address_line1: '4 Dock Road',
  address_line2: null,
  city: 'Bristol',
  postcode: 'BS1 6EG',
  country: 'GB',
  vat_number: 'GB987654321',
  email: null,
  archived_at: null,
  created_at: '2026-07-20T00:00:00Z',
  updated_at: '2026-07-20T00:00:00Z',
}

const DRAFT = {
  id: 7,
  status: 'draft',
  number: null,
  client_id: 1,
  invoice_date: null,
  tax_point_date: null,
  due_date: null,
  currency: 'GBP',
  notes: null,
  lines: [
    {
      id: 1,
      position: 1,
      description: 'Consulting',
      quantity: '2.000',
      unit_price: '10.0000',
      vat_rate_code: 'standard',
    },
  ],
  snapshot: null,
  issued_at: null,
  created_at: '2026-07-20T00:00:00Z',
  updated_at: '2026-07-20T00:00:00Z',
}

// The exact strings the server would return. The panel must show these and
// nothing else — no rounding, no recomputation, no formatting beyond £ and
// thousands separators.
const SERVER_TOTALS = {
  groups: [
    { code: 'standard', rate: '0.2000', net: '1300.00', vat: '260.00', gross: '1560.00' },
  ],
  total_net: '1300.00',
  total_vat: '260.00',
  total_gross: '1560.00',
}

let previewCalls = 0

const server = setupServer(
  http.get('/api/v1/clients', () => HttpResponse.json([CLIENT])),
  http.get('/api/v1/invoices/7', () => HttpResponse.json(DRAFT)),
  http.post('/api/v1/invoices/preview-totals', () => {
    previewCalls += 1
    return HttpResponse.json(SERVER_TOTALS)
  }),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

beforeEach(() => {
  previewCalls = 0
})

function renderEditor() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/invoices/7/edit']}>
        <Routes>
          <Route path="/invoices/:id/edit" element={<InvoiceEditor />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('invoice editor live totals', () => {
  it('shows exactly the server-returned strings after the debounce', async () => {
    // Real timers throughout: the debounce is 400 ms, so waiting it out is
    // cheaper and less brittle than faking the clock under user-event.
    const user = userEvent.setup()
    renderEditor()

    await screen.findByDisplayValue('Consulting')

    const unitPrice = screen.getByLabelText('Unit price 1')
    await user.clear(unitPrice)
    await user.type(unitPrice, '650.0000')

    await waitFor(
      () => {
        expect(screen.getByTestId('total-net').textContent).toBe('£1,300.00')
      },
      { timeout: 3000 },
    )

    expect(screen.getByTestId('total-vat').textContent).toBe('£260.00')
    expect(screen.getByTestId('total-gross').textContent).toBe('£1,560.00')
  })

  it('shows a dash and fires no request while a line is invalid', async () => {
    const user = userEvent.setup()
    renderEditor()

    await screen.findByDisplayValue('Consulting')
    previewCalls = 0

    const unitPrice = screen.getByLabelText('Unit price 1')
    await user.clear(unitPrice)
    await user.type(unitPrice, '1,5') // comma decimal mark — rejected by validation

    await waitFor(() => {
      expect(screen.getByTestId('total-net').textContent).toBe('—')
    })

    // Well past the 400 ms debounce: an invalid line must never reach the server.
    await new Promise((resolve) => setTimeout(resolve, 700))
    expect(previewCalls).toBe(0)
    expect(screen.getByTestId('total-gross').textContent).toBe('—')
  })

  it('drops stale totals the moment the lines change', async () => {
    const user = userEvent.setup()
    renderEditor()

    await screen.findByDisplayValue('Consulting')
    await waitFor(() => {
      expect(screen.getByTestId('total-net').textContent).toBe('£1,300.00')
    })

    // Editing invalidates what is on screen immediately — stale numbers under
    // new inputs would read as current.
    const description = screen.getByLabelText('Description 1')
    await user.type(description, ' extra')

    expect(screen.getByTestId('total-net').textContent).toBe('—')
  })
})

describe('issue dialog', () => {
  it('renders the server message when issuing is refused', async () => {
    server.use(
      http.get('/api/v1/invoices/7/totals', () => HttpResponse.json(SERVER_TOTALS)),
      http.post('/api/v1/invoices/7/issue', () =>
        HttpResponse.json(
          {
            detail: {
              code: 'company_profile_missing',
              message: 'Set up the company profile before issuing.',
            },
          },
          { status: 409 },
        ),
      ),
    )

    const user = userEvent.setup()
    renderEditor()

    await screen.findByDisplayValue('Consulting')
    await user.click(screen.getByRole('button', { name: 'Issue…' }))

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Issue invoice' }))

    // The server's own wording, not ours.
    expect(await screen.findByText('Set up the company profile before issuing.')).toBeTruthy()
  })
})
