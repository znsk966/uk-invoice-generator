import { ApiError } from '../api/client'

/**
 * Inline alert for a failed request. Shows the **server's** message verbatim —
 * the server owns the domain rules, so it owns their wording. We only supply a
 * fallback when the failure did not come from the API at all.
 */
export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null

  const message =
    error instanceof ApiError
      ? error.message
      : 'Something went wrong. Check that the backend is running.'

  return (
    <div
      role="alert"
      className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      {message}
    </div>
  )
}
