import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { MemoryRouter } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'

import App from '../App'

// A logged-out backend: /me is 401, and the domain lists would be too.
function anonymousHandlers() {
  return [
    http.get('/api/v1/auth/me', () =>
      HttpResponse.json(
        { detail: { code: 'not_authenticated', message: 'Not authenticated.' } },
        { status: 401 },
      ),
    ),
  ]
}

const server = setupServer(...anonymousHandlers())

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers(...anonymousHandlers()))
afterAll(() => server.close())

function renderApp(initialPath = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('route guard', () => {
  it('redirects an anonymous visitor to the sign-in page', async () => {
    renderApp('/invoices')
    // The guard sees /me → 401 and routes to /login.
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeTruthy()
  })
})

describe('login form', () => {
  it('shows the server message when credentials are rejected', async () => {
    server.use(
      http.post('/api/v1/auth/login', () =>
        HttpResponse.json(
          { detail: { code: 'invalid_credentials', message: 'Incorrect email or password.' } },
          { status: 401 },
        ),
      ),
    )

    const user = userEvent.setup()
    renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'nobody@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    // The server's own wording, verbatim.
    expect(await screen.findByText('Incorrect email or password.')).toBeTruthy()
  })

  it('lands the user in the app after a successful sign-in', async () => {
    server.use(
      http.post('/api/v1/auth/login', () =>
        HttpResponse.json({ id: 1, email: 'owner@example.com' }),
      ),
      http.get('/api/v1/invoices', () => HttpResponse.json([])),
    )

    const user = userEvent.setup()
    renderApp('/login')

    await user.type(await screen.findByLabelText('Email'), 'owner@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    // The invoices page (and its sidebar) replaces the sign-in form.
    expect(await screen.findByText('owner@example.com')).toBeTruthy()
  })
})

describe('logout', () => {
  it('clears auth state and returns to sign-in', async () => {
    // Start authenticated.
    server.use(
      http.get('/api/v1/auth/me', () => HttpResponse.json({ id: 1, email: 'owner@example.com' })),
      http.get('/api/v1/invoices', () => HttpResponse.json([])),
      http.post('/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
    )

    const user = userEvent.setup()
    renderApp('/invoices')

    // Sidebar shows the user; click Log out.
    await user.click(await screen.findByRole('button', { name: 'Log out' }))

    // Back to the sign-in form.
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeTruthy()
  })
})
