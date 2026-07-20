import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { archiveClient, listClients, unarchiveClient } from '../api/clients'
import type { Client } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorAlert } from '../components/ErrorAlert'

export function ClientsList() {
  const [includeArchived, setIncludeArchived] = useState(false)
  const [pendingArchive, setPendingArchive] = useState<Client | null>(null)
  const queryClient = useQueryClient()

  const clients = useQuery({
    queryKey: ['clients', includeArchived],
    queryFn: () => listClients(includeArchived),
  })

  const archive = useMutation({
    mutationFn: (id: number) => archiveClient(id),
    onSuccess: () => {
      setPendingArchive(null)
      void queryClient.invalidateQueries({ queryKey: ['clients'] })
    },
  })

  const unarchive = useMutation({
    mutationFn: (id: number) => unarchiveClient(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['clients'] }),
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight">Clients</h2>
        <Link
          to="/clients/new"
          className="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          New Client
        </Link>
      </div>

      <ErrorAlert error={clients.error ?? archive.error ?? unarchive.error} />

      <label className="mb-4 flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(event) => setIncludeArchived(event.target.checked)}
        />
        Show archived
      </label>

      {clients.isPending ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : clients.data && clients.data.length > 0 ? (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4 font-medium">Name</th>
              <th className="py-2 pr-4 font-medium">City</th>
              <th className="py-2 pr-4 font-medium">VAT number</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {clients.data.map((client) => {
              const archived = client.archived_at !== null
              return (
                <tr
                  key={client.id}
                  className={`border-b border-gray-100 ${archived ? 'text-gray-400' : ''}`}
                >
                  <td className="py-2 pr-4">{client.name}</td>
                  <td className="py-2 pr-4">{client.city}</td>
                  <td className="py-2 pr-4">{client.vat_number ?? '—'}</td>
                  <td className="py-2 pr-4">{archived ? 'Archived' : 'Active'}</td>
                  <td className="py-2 text-right">
                    {archived ? (
                      <button
                        type="button"
                        onClick={() => unarchive.mutate(client.id)}
                        className="text-sm text-gray-700 underline underline-offset-4 hover:text-gray-900"
                      >
                        Unarchive
                      </button>
                    ) : (
                      <span className="flex justify-end gap-3">
                        <Link
                          to={`/clients/${client.id}/edit`}
                          className="text-sm underline underline-offset-4"
                        >
                          Edit
                        </Link>
                        <button
                          type="button"
                          onClick={() => setPendingArchive(client)}
                          className="text-sm underline underline-offset-4"
                        >
                          Archive
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      ) : (
        <p className="text-sm text-gray-500">No clients yet.</p>
      )}

      {pendingArchive ? (
        <ConfirmDialog
          title={`Archive ${pendingArchive.name}?`}
          confirmLabel="Archive"
          busy={archive.isPending}
          onCancel={() => setPendingArchive(null)}
          onConfirm={() => archive.mutate(pendingArchive.id)}
        >
          <p>
            Archived clients cannot be put on new invoices. Invoices already issued to
            them stay readable — they render from their own snapshot. You can unarchive
            at any time.
          </p>
        </ConfirmDialog>
      ) : null}
    </div>
  )
}
