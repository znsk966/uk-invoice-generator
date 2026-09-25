import { request } from './client'
import type { LoginRequest, RegisterRequest, User } from './types'

/**
 * The current user, or throws `ApiError` with code `not_authenticated`.
 *
 * `allow401`: a 401 here is the normal "not logged in yet" answer, not a
 * session that just died mid-session — so it must not trigger the global
 * redirect (that would fight the route guard that already sends anonymous users
 * to /login).
 */
export function getMe(): Promise<User> {
  return request<User>('/auth/me', { allow401: true })
}

export function register(payload: RegisterRequest): Promise<User> {
  // A failed registration (e.g. email_taken) is shown on the form, not redirected.
  return request<User>('/auth/register', { method: 'POST', body: payload, allow401: true })
}

export function login(payload: LoginRequest): Promise<User> {
  return request<User>('/auth/login', { method: 'POST', body: payload, allow401: true })
}

export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' })
}
