import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import { ProductForm } from './ProductForm'

const PRODUCT = {
  id: 3,
  code: 'CONS-1H',
  description: 'Consulting, per hour',
  kind: 'service',
  vat_rate_code: 'standard',
  unit_price: '95.0000',
  archived_at: null,
  created_at: '2026-09-25T00:00:00Z',
  updated_at: '2026-09-25T00:00:00Z',
}

let patchBodies: unknown[] = []

const server = setupServer(
  http.get('/api/v1/products/3', () => HttpResponse.json(PRODUCT)),
  http.patch('/api/v1/products/3', async ({ request }) => {
    const body = (await request.json()) as { unit_price: string }
    patchBodies.push(body)
    return HttpResponse.json({ ...PRODUCT, unit_price: body.unit_price })
  }),
  http.get('/api/v1/products', () => HttpResponse.json([PRODUCT])),
)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  patchBodies = []
})
afterAll(() => server.close())

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/products/new" element={<ProductForm />} />
          <Route path="/products/:id/edit" element={<ProductForm />} />
          <Route path="/products" element={<p>products list</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('edit product form', () => {
  it('exposes only the price as an editable field', async () => {
    renderAt('/products/3/edit')
    await screen.findByText('Edit product')

    // Exactly one form control besides the buttons: the price.
    const inputs = screen.queryAllByRole('textbox')
    expect(inputs).toHaveLength(1)
    expect((inputs[0] as HTMLInputElement).value).toBe('95.0000')
    expect(screen.queryAllByRole('combobox')).toHaveLength(0)

    // Identity is shown, read-only, as text.
    expect(screen.getByText('CONS-1H')).toBeTruthy()
    expect(screen.getByText('Consulting, per hour')).toBeTruthy()
    expect(screen.getByText('service')).toBeTruthy()
    expect(screen.getByText('standard')).toBeTruthy()
    expect(
      screen.getByText(
        "Description and VAT rate can't be changed after creation. Archive this product and create a new one.",
      ),
    ).toBeTruthy()
  })

  it('saves by sending only the price', async () => {
    const user = userEvent.setup()
    renderAt('/products/3/edit')
    const price = await screen.findByDisplayValue('95.0000')

    await user.clear(price)
    await user.type(price, '120.5000')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await screen.findByText('products list')
    expect(patchBodies).toEqual([{ unit_price: '120.5000' }])
  })
})

describe('new product form', () => {
  it('makes every field editable', async () => {
    renderAt('/products/new')
    await screen.findByText('New product')
    // Code, description, price; kind and VAT as selects.
    expect(screen.getAllByRole('textbox')).toHaveLength(3)
    expect(screen.getAllByRole('combobox')).toHaveLength(2)
  })
})
