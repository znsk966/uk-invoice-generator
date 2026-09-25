/**
 * The single fetch wrapper every API module goes through.
 *
 * The backend renders every handled error as
 * `{"detail": {"code": "...", "message": "..."}}`, so failures are unwrapped
 * into a typed `ApiError` carrying the stable machine `code` (branch on this)
 * and the server's `message` (show this to the user — never invent our own
 * wording for a server-side rule).
 */

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/** Error codes the UI branches on. Mirrors backend `app/core/errors.py`. */
export const ERROR_CODES = {
  notFound: 'not_found',
  clientArchived: 'client_archived',
  invoiceNotDraft: 'invoice_not_draft',
  invoiceNotIssued: 'invoice_not_issued',
  validationFailed: 'validation_failed',
  companyProfileMissing: 'company_profile_missing',
  emailTaken: 'email_taken',
  invalidCredentials: 'invalid_credentials',
  notAuthenticated: 'not_authenticated',
} as const

const BASE_URL = '/api/v1'

/**
 * Called whenever any request comes back 401. `App` registers a handler that
 * drops the cached user and navigates to /login. Kept as a registered callback
 * (not a hard `window.location` redirect) so it can use the SPA router and
 * preserve a return-to path. Endpoints that legitimately expect a 401 (the
 * `useMe` probe, the login form) opt out with `allow401`.
 */
type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler = () => {}

export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler
}

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
  /** When true, a 401 is returned as an ApiError without triggering the global
   *  redirect — for the auth probe and the login/register forms themselves. */
  allow401?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, allow401 = false } = options

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    signal,
    // Send and accept the HTTP-only session cookie on every request.
    credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (response.status === 401 && !allow401) {
    // Session gone or never established: let the app tear down auth state and
    // route to login before surfacing the error to the caller.
    onUnauthorized()
  }

  if (response.status === 204) {
    return undefined as T
  }

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    throw toApiError(response.status, payload)
  }

  return payload as T
}

function toApiError(status: number, payload: unknown): ApiError {
  const detail = (payload as { detail?: unknown } | null)?.detail

  if (detail && typeof detail === 'object' && 'code' in detail && 'message' in detail) {
    const { code, message } = detail as { code: unknown; message: unknown }
    return new ApiError(status, String(code), String(message))
  }

  // Anything that did not come from our error handlers (a proxy error, a 500
  // from an unhandled exception). Keep it honest rather than guessing a code.
  return new ApiError(status, 'unexpected_error', `Request failed with status ${status}.`)
}
