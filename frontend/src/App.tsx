import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { useEffect, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { setUnauthorizedHandler } from './api/client'
import { Layout } from './components/Layout'
import { ClientForm } from './pages/ClientForm'
import { ClientsList } from './pages/ClientsList'
import { InvoiceEditor } from './pages/InvoiceEditor'
import { InvoicesList } from './pages/InvoicesList'
import { InvoiceView } from './pages/InvoiceView'
import { ProductForm } from './pages/ProductForm'
import { ProductsList } from './pages/ProductsList'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { Settings } from './pages/Settings'
import { ME_QUERY_KEY, useMe } from './shared/useMe'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 404 or a 409 is an answer, not a hiccup — retrying it just delays
      // showing the user what the server said.
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
})

/** A neutral placeholder while the auth probe is in flight (avoids a flash of
 *  the login page for an already-authenticated user, or vice versa). */
function AuthPending() {
  return <div className="min-h-screen bg-gray-50" />
}

/** Gate for the app proper: anonymous users are sent to /login, remembering
 *  where they were so login can return them there. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useMe()
  const location = useLocation()
  if (isPending) return <AuthPending />
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  return <>{children}</>
}

/** Gate for /login and /register: an already-authenticated user is sent on to
 *  the app rather than shown a sign-in form. */
function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useMe()
  if (isPending) return <AuthPending />
  if (user) return <Navigate to="/invoices" replace />
  return <>{children}</>
}

/** Wire the client's global 401 handler to SPA navigation: when any request
 *  reports the session is gone, drop the cached user and route to /login. */
function useUnauthorizedRedirect() {
  const client = useQueryClient()
  const navigate = useNavigate()
  useEffect(() => {
    setUnauthorizedHandler(() => {
      client.setQueryData(ME_QUERY_KEY, null)
      navigate('/login', { replace: true })
    })
    return () => setUnauthorizedHandler(() => {})
  }, [client, navigate])
}

function AppRoutes() {
  useUnauthorizedRedirect()
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <Login />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthed>
            <Register />
          </RedirectIfAuthed>
        }
      />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/invoices" replace />} />
        <Route path="/invoices" element={<InvoicesList />} />
        <Route path="/invoices/new" element={<InvoiceEditor />} />
        <Route path="/invoices/:id" element={<InvoiceView />} />
        <Route path="/invoices/:id/edit" element={<InvoiceEditor />} />
        <Route path="/clients" element={<ClientsList />} />
        <Route path="/clients/new" element={<ClientForm />} />
        <Route path="/clients/:id/edit" element={<ClientForm />} />
        <Route path="/products" element={<ProductsList />} />
        <Route path="/products/new" element={<ProductForm />} />
        <Route path="/products/:id/edit" element={<ProductForm />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/invoices" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppRoutes />
    </QueryClientProvider>
  )
}
