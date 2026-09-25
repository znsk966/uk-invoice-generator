import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { createProduct, getProduct, updateProductPrice } from '../api/products'
import type { Product, ProductCreate, ProductKind, VatRateCode } from '../api/types'
import { PRODUCT_KINDS, VAT_RATE_CODES } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { Field } from '../components/Field'
import { formatMoney, isValidMoneyInput } from '../shared/money'

const EMPTY: ProductCreate = {
  code: '',
  description: '',
  kind: 'service',
  vat_rate_code: 'standard',
  unit_price: '0.0000',
}

/**
 * Create: every field is editable. Edit: **only the price** — a product's code,
 * description, kind and VAT rate are its identity and are fixed at creation
 * (the server refuses to change them, and so does the database).
 */
export function ProductForm() {
  const { id } = useParams()
  const productId = id ? Number(id) : null

  const existing = useQuery({
    queryKey: ['product', productId],
    queryFn: () => getProduct(productId as number),
    enabled: productId !== null,
  })

  if (productId === null) return <CreateProductForm />
  if (existing.error) return <ErrorAlert error={existing.error} />
  if (!existing.data) return <p className="text-sm text-gray-500">Loading…</p>
  return <EditPriceForm product={existing.data} />
}

function CreateProductForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ProductCreate>(EMPTY)

  const save = useMutation({
    mutationFn: createProduct,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['products'] })
      navigate('/products')
    },
  })

  const set = (change: Partial<ProductCreate>) => setForm((current) => ({ ...current, ...change }))
  const priceValid = isValidMoneyInput(form.unit_price)

  return (
    <div className="max-w-2xl">
      <h2 className="mb-6 text-2xl font-semibold tracking-tight">New product</h2>

      <ErrorAlert error={save.error} />

      <p className="mb-4 text-sm text-gray-600">
        Code, description, kind and VAT rate can't be changed after creation. Only the price
        can.
      </p>

      <form
        className="grid grid-cols-2 gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (priceValid) save.mutate(form)
        }}
      >
        <Field label="Code" value={form.code} onChange={(code) => set({ code })} required />
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-gray-700">Kind</span>
          <select
            value={form.kind}
            onChange={(event) => set({ kind: event.target.value as ProductKind })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm capitalize"
          >
            {PRODUCT_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
        </label>
        <div className="col-span-2">
          <Field
            label="Description"
            value={form.description}
            onChange={(description) => set({ description })}
            required
          />
        </div>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-gray-700">VAT rate</span>
          <select
            value={form.vat_rate_code}
            onChange={(event) => set({ vat_rate_code: event.target.value as VatRateCode })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm capitalize"
          >
            {VAT_RATE_CODES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <PriceInput value={form.unit_price} onChange={(unit_price) => set({ unit_price })} />

        <FormButtons busy={save.isPending} disabled={!priceValid} />
      </form>
    </div>
  )
}

function EditPriceForm({ product }: { product: Product }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [price, setPrice] = useState(product.unit_price)

  useEffect(() => setPrice(product.unit_price), [product.unit_price])

  const save = useMutation({
    mutationFn: (unit_price: string) => updateProductPrice(product.id, { unit_price }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['products'] })
      void queryClient.invalidateQueries({ queryKey: ['product', product.id] })
      navigate('/products')
    },
  })

  const priceValid = isValidMoneyInput(price)

  return (
    <div className="max-w-2xl">
      <h2 className="mb-6 text-2xl font-semibold tracking-tight">Edit product</h2>

      <ErrorAlert error={save.error} />

      <dl className="mb-2 grid grid-cols-2 gap-4 rounded-md border border-gray-200 bg-gray-50 p-4 text-sm">
        <ReadOnly label="Code" value={product.code} mono />
        <ReadOnly label="Kind" value={product.kind} capitalize />
        <div className="col-span-2">
          <ReadOnly label="Description" value={product.description} />
        </div>
        <ReadOnly label="VAT rate" value={product.vat_rate_code} capitalize />
        <ReadOnly label="Current price" value={formatMoney(product.unit_price)} />
      </dl>
      <p className="mb-6 text-sm text-gray-600">
        Description and VAT rate can't be changed after creation. Archive this product and
        create a new one.
      </p>

      <form
        className="grid grid-cols-2 gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (priceValid) save.mutate(price)
        }}
      >
        <PriceInput value={price} onChange={setPrice} />
        <p className="self-end pb-2 text-xs text-gray-500">
          Applies to new invoice lines only. Existing lines keep their price.
        </p>
        <FormButtons busy={save.isPending} disabled={!priceValid} />
      </form>
    </div>
  )
}

function ReadOnly({
  label,
  value,
  mono = false,
  capitalize = false,
}: {
  label: string
  value: string
  mono?: boolean
  capitalize?: boolean
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-gray-500">{label}</dt>
      <dd
        className={`mt-0.5 text-gray-900 ${mono ? 'font-mono text-xs' : ''} ${
          capitalize ? 'capitalize' : ''
        }`}
      >
        {value}
      </dd>
    </div>
  )
}

/** `type="text" inputMode="decimal"`, never `type="number"` (float-shaped value). */
function PriceInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const valid = isValidMoneyInput(value)
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">
        Unit price (£)<span className="text-red-600"> *</span>
      </span>
      <input
        type="text"
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`w-full rounded-md border px-3 py-2 text-right text-sm tabular-nums ${
          valid ? 'border-gray-300' : 'border-red-400 bg-red-50'
        }`}
      />
    </label>
  )
}

function FormButtons({ busy, disabled }: { busy: boolean; disabled: boolean }) {
  const navigate = useNavigate()
  return (
    <div className="col-span-2 mt-2 flex gap-2">
      <button
        type="submit"
        disabled={busy || disabled}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
      >
        {busy ? 'Saving…' : 'Save'}
      </button>
      <button
        type="button"
        onClick={() => navigate('/products')}
        className="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
      >
        Cancel
      </button>
    </div>
  )
}
