import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from './components/Layout'
import { ClientForm } from './pages/ClientForm'
import { ClientsList } from './pages/ClientsList'
import { InvoiceEditor } from './pages/InvoiceEditor'
import { InvoicesList } from './pages/InvoicesList'
import { InvoiceView } from './pages/InvoiceView'
import { Settings } from './pages/Settings'

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

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/invoices" replace />} />
          <Route path="/invoices" element={<InvoicesList />} />
          <Route path="/invoices/new" element={<InvoiceEditor />} />
          <Route path="/invoices/:id" element={<InvoiceView />} />
          <Route path="/invoices/:id/edit" element={<InvoiceEditor />} />
          <Route path="/clients" element={<ClientsList />} />
          <Route path="/clients/new" element={<ClientForm />} />
          <Route path="/clients/:id/edit" element={<ClientForm />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/invoices" replace />} />
        </Route>
      </Routes>
    </QueryClientProvider>
  )
}
