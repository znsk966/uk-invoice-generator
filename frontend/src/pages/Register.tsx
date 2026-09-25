import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { register } from '../api/auth'
import type { User } from '../api/types'
import { ErrorAlert } from '../components/ErrorAlert'
import { ME_QUERY_KEY } from '../shared/useMe'
import { AuthCard, AuthInput } from './Login'

export function Register() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')

  // Client-side confirmation is a presence + match check only — no strength
  // meter. The server owns the real rule (minimum length).
  const mismatch = confirm.length > 0 && password !== confirm

  const submit = useMutation({
    mutationFn: () => register({ email, password }),
    onSuccess: (user: User) => {
      // Registration logs the user in (the server set the cookie).
      queryClient.setQueryData(ME_QUERY_KEY, user)
      navigate('/invoices', { replace: true })
    },
  })

  return (
    <AuthCard title="Create an account">
      <ErrorAlert error={submit.error} />
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (password !== confirm) return
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
          autoComplete="new-password"
        />
        <AuthInput
          label="Confirm password"
          type="password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
        />
        {mismatch ? <p className="text-sm text-red-700">Passwords do not match.</p> : null}
        <button
          type="submit"
          disabled={submit.isPending || mismatch || password.length === 0}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
        >
          {submit.isPending ? 'Creating…' : 'Create account'}
        </button>
      </form>
      <p className="mt-4 text-sm text-gray-600">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-gray-900 underline">
          Sign in
        </Link>
      </p>
    </AuthCard>
  )
}
