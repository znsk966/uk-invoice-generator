import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { createClient, getClient, updateClient } from '../api/clients'
import type { ClientWrite } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { Field } from '../components/Field'

const EMPTY: ClientWrite = {
  name: '',
  address_line1: '',
  address_line2: null,
  city: '',
  postcode: '',
  country: 'GB',
  vat_number: null,
  email: null,
}

/** One form for both create and edit. There is no delete — clients are archived. */
export function ClientForm() {
  const { id } = useParams()
  const clientId = id ? Number(id) : null
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ClientWrite>(EMPTY)

  const existing = useQuery({
    queryKey: ['client', clientId],
    queryFn: () => getClient(clientId as number),
    enabled: clientId !== null,
  })

  useEffect(() => {
    if (!existing.data) return
    const { name, address_line1, address_line2, city, postcode, country, vat_number, email } =
      existing.data
    setForm({ name, address_line1, address_line2, city, postcode, country, vat_number, email })
  }, [existing.data])

  const save = useMutation({
    mutationFn: (payload: ClientWrite) =>
      clientId === null ? createClient(payload) : updateClient(clientId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['clients'] })
      navigate('/clients')
    },
  })

  const set = (key: keyof ClientWrite) => (value: string) =>
    setForm((current) => ({ ...current, [key]: value === '' ? nullableDefault(key) : value }))

  return (
    <div className="max-w-2xl">
      <h2 className="mb-6 text-2xl font-semibold tracking-tight">
        {clientId === null ? 'New client' : 'Edit client'}
      </h2>

      <ErrorAlert error={save.error ?? existing.error} />

      <form
        className="grid grid-cols-2 gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(form)
        }}
      >
        <div className="col-span-2">
          <Field label="Name" value={form.name} onChange={set('name')} required />
        </div>
        <div className="col-span-2">
          <Field
            label="Address line 1"
            value={form.address_line1}
            onChange={set('address_line1')}
            required
          />
        </div>
        <div className="col-span-2">
          <Field
            label="Address line 2"
            value={form.address_line2 ?? ''}
            onChange={set('address_line2')}
          />
        </div>
        <Field label="City" value={form.city} onChange={set('city')} required />
        <Field label="Postcode" value={form.postcode} onChange={set('postcode')} required />
        <Field label="Country" value={form.country} onChange={set('country')} required />
        <Field label="VAT number" value={form.vat_number ?? ''} onChange={set('vat_number')} />
        <div className="col-span-2">
          <Field label="Email" value={form.email ?? ''} onChange={set('email')} />
        </div>

        <div className="col-span-2 mt-2 flex gap-2">
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/clients')}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}

/** Required fields stay `''`; optional ones go back to `null` when cleared. */
function nullableDefault(key: keyof ClientWrite): string | null {
  return key === 'address_line2' || key === 'vat_number' || key === 'email' ? null : ''
}
