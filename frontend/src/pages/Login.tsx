import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { login } from '../api/auth'
import type { User } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { ME_QUERY_KEY } from '../shared/useMe'

export function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // Where to go after login: back to the page the guard bounced us from, else
  // the invoices list.
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname
  const returnTo = from && from !== '/login' ? from : '/invoices'

  const submit = useMutation({
    mutationFn: () => login({ email, password }),
    onSuccess: (user: User) => {
      queryClient.setQueryData(ME_QUERY_KEY, user)
      navigate(returnTo, { replace: true })
    },
  })

  return (
    <AuthCard title="Sign in">
      <ErrorAlert error={submit.error} />
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          submit.mutate()
        }}
      >
        <AuthInput
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="username"
        />
        <AuthInput
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />
        <button
          type="submit"
          disabled={submit.isPending}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {submit.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="mt-4 text-sm text-gray-600">
        No account?{' '}
        <Link to="/register" className="font-medium text-gray-900 underline">
          Create one
        </Link>
      </p>
    </AuthCard>
  )
}

// --- small building blocks shared by Login and Register ------------------- //

export function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-1 text-lg font-semibold tracking-tight text-gray-900">
          UK Invoice Generator
        </h1>
        <h2 className="mb-6 text-sm text-gray-500">{title}</h2>
        {children}
      </div>
    </div>
  )
}

export function AuthInput({
  label,
  type,
  value,
  onChange,
  autoComplete,
}: {
  label: string
  type: 'email' | 'password'
  value: string
  onChange: (value: string) => void
  autoComplete?: string
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">{label}</span>
      <input
        type={type}
        value={value}
        required
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
      />
    </label>
  )
}
