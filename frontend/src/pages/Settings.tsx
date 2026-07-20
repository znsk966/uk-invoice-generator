import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { ApiError, ERROR_CODES } from '../api/client'
import { getCompanyProfile, saveCompanyProfile } from '../api/company'
import type { CompanyProfile, CompanyProfileWrite } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { Field } from '../components/Field'

const EMPTY: CompanyProfileWrite = {
  trading_name: '',
  address_line1: '',
  address_line2: null,
  city: '',
  postcode: '',
  country: 'GB',
  vat_number: null,
  company_number: null,
  email: null,
  phone: null,
  bank_account_name: null,
  bank_sort_code: null,
  bank_account_number: null,
}

function toWritable(profile: CompanyProfile): CompanyProfileWrite {
  return {
    trading_name: profile.trading_name,
    address_line1: profile.address_line1,
    address_line2: profile.address_line2,
    city: profile.city,
    postcode: profile.postcode,
    country: profile.country,
    vat_number: profile.vat_number,
    company_number: profile.company_number,
    email: profile.email,
    phone: profile.phone,
    bank_account_name: profile.bank_account_name,
    bank_sort_code: profile.bank_sort_code,
    bank_account_number: profile.bank_account_number,
  }
}

const OPTIONAL: (keyof CompanyProfileWrite)[] = [
  'address_line2',
  'vat_number',
  'company_number',
  'email',
  'phone',
  'bank_account_name',
  'bank_sort_code',
  'bank_account_number',
]

export function Settings() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<CompanyProfileWrite>(EMPTY)
  const [saved, setSaved] = useState(false)

  const profile = useQuery({
    queryKey: ['company-profile'],
    queryFn: getCompanyProfile,
    // A missing profile is an expected state on a fresh install, not a failure
    // to retry at.
    retry: false,
  })

  useEffect(() => {
    if (!profile.data) return
    // Copy only the editable fields; id/created_at/updated_at are server-owned.
    setForm(toWritable(profile.data))
  }, [profile.data])

  const save = useMutation({
    mutationFn: (payload: CompanyProfileWrite) => saveCompanyProfile(payload),
    onSuccess: () => {
      setSaved(true)
      void queryClient.invalidateQueries({ queryKey: ['company-profile'] })
    },
  })

  const missing =
    profile.error instanceof ApiError &&
    profile.error.code === ERROR_CODES.companyProfileMissing

  const set = (key: keyof CompanyProfileWrite) => (value: string) =>
    setForm((current) => ({
      ...current,
      [key]: value === '' && OPTIONAL.includes(key) ? null : value,
    }))

  return (
    <div className="max-w-2xl">
      <h2 className="mb-6 text-2xl font-semibold tracking-tight">Company profile</h2>

      {missing ? (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          No company profile saved yet. Invoices cannot be issued until this is filled
          in — the seller’s details are frozen into every issued invoice.
        </div>
      ) : (
        <ErrorAlert error={profile.error} />
      )}

      <ErrorAlert error={save.error} />

      {saved && !save.isPending && !save.error ? (
        <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          Company profile saved.
        </div>
      ) : null}

      <form
        className="grid grid-cols-2 gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          setSaved(false)
          save.mutate(form)
        }}
      >
        <div className="col-span-2">
          <Field
            label="Trading name"
            value={form.trading_name}
            onChange={set('trading_name')}
            required
          />
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
        <Field
          label="Company number"
          value={form.company_number ?? ''}
          onChange={set('company_number')}
        />
        <Field label="Email" value={form.email ?? ''} onChange={set('email')} />
        <Field label="Phone" value={form.phone ?? ''} onChange={set('phone')} />

        <h3 className="col-span-2 mt-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Bank details
        </h3>
        <div className="col-span-2">
          <Field
            label="Account name"
            value={form.bank_account_name ?? ''}
            onChange={set('bank_account_name')}
          />
        </div>
        <Field
          label="Sort code"
          value={form.bank_sort_code ?? ''}
          onChange={set('bank_sort_code')}
          placeholder="00-00-00"
        />
        <Field
          label="Account number"
          value={form.bank_account_number ?? ''}
          onChange={set('bank_account_number')}
        />

        <div className="col-span-2 mt-2">
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  )
}
