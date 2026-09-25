import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { archiveProduct, listProducts, unarchiveProduct } from '../api/products'
import type { Product } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorAlert } from '../components/ErrorAlert'
import { formatMoney } from '../shared/money'

export function ProductsList() {
  const [includeArchived, setIncludeArchived] = useState(false)
  const [pendingArchive, setPendingArchive] = useState<Product | null>(null)
  const [pendingUnarchive, setPendingUnarchive] = useState<Product | null>(null)
  const queryClient = useQueryClient()

  const products = useQuery({
    queryKey: ['products', includeArchived],
    queryFn: () => listProducts(includeArchived),
  })

  const archive = useMutation({
    mutationFn: (id: number) => archiveProduct(id),
    onSuccess: () => {
      setPendingArchive(null)
      void queryClient.invalidateQueries({ queryKey: ['products'] })
    },
  })

  const unarchive = useMutation({
    mutationFn: (id: number) => unarchiveProduct(id),
    onSuccess: () => {
      setPendingUnarchive(null)
      void queryClient.invalidateQueries({ queryKey: ['products'] })
    },
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-semibold tracking-tight">Products</h2>
        <Link
          to="/products/new"
          className="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          New Product
        </Link>
      </div>

      <ErrorAlert error={products.error ?? archive.error ?? unarchive.error} />

      <label className="mb-4 flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(event) => setIncludeArchived(event.target.checked)}
        />
        Show archived
      </label>

      {products.isPending ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : products.data && products.data.length > 0 ? (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4 font-medium">Code</th>
              <th className="py-2 pr-4 font-medium">Description</th>
              <th className="py-2 pr-4 font-medium">Kind</th>
              <th className="py-2 pr-4 font-medium">VAT rate</th>
              <th className="py-2 pr-4 text-right font-medium">Price</th>
              <th className="py-2 pr-4 font-medium">Status</th>
              <th className="py-2 font-medium" />
            </tr>
          </thead>
          <tbody>
            {products.data.map((product) => {
              const archived = product.archived_at !== null
              return (
                <tr
                  key={product.id}
                  className={`border-b border-gray-100 ${archived ? 'text-gray-400' : ''}`}
                >
                  <td className="py-2 pr-4 font-mono text-xs">{product.code}</td>
                  <td className="py-2 pr-4">{product.description}</td>
                  <td className="py-2 pr-4 capitalize">{product.kind}</td>
                  <td className="py-2 pr-4 capitalize">{product.vat_rate_code}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {formatMoney(product.unit_price)}
                  </td>
                  <td className="py-2 pr-4">{archived ? 'Archived' : 'Active'}</td>
                  <td className="py-2 text-right">
                    {archived ? (
                      <button
                        type="button"
                        onClick={() => setPendingUnarchive(product)}
                        className="text-sm text-gray-700 underline underline-offset-4 hover:text-gray-900"
                      >
                        Unarchive
                      </button>
                    ) : (
                      <span className="flex justify-end gap-3">
                        <Link
                          to={`/products/${product.id}/edit`}
                          className="text-sm underline underline-offset-4"
                        >
                          Edit price
                        </Link>
                        <button
                          type="button"
                          onClick={() => setPendingArchive(product)}
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
        <p className="text-sm text-gray-500">No products yet.</p>
      )}

      {pendingArchive ? (
        <ConfirmDialog
          title={`Archive ${pendingArchive.code}?`}
          confirmLabel="Archive"
          busy={archive.isPending}
          onCancel={() => setPendingArchive(null)}
          onConfirm={() => archive.mutate(pendingArchive.id)}
        >
          <p>
            Archived products cannot be added to new invoice lines. Drafts that already use
            it keep it, and issued invoices are unaffected. You can unarchive at any time.
          </p>
        </ConfirmDialog>
      ) : null}

      {pendingUnarchive ? (
        <ConfirmDialog
          title={`Unarchive ${pendingUnarchive.code}?`}
          confirmLabel="Unarchive"
          busy={unarchive.isPending}
          onCancel={() => setPendingUnarchive(null)}
          onConfirm={() => unarchive.mutate(pendingUnarchive.id)}
        >
          <p>The product becomes available for new invoice lines again.</p>
        </ConfirmDialog>
      ) : null}
    </div>
  )
}
