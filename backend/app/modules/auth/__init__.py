"""Authentication and per-user ownership.

Registration, login, logout, and the ``current_user`` dependency every domain
router now depends on. Sessions are opaque random tokens stored only as their
SHA-256 hash; the raw token lives solely in the client's HTTP-only cookie.

Deliberately **out of scope** for this PoC (documented here so nobody wonders):
email verification, password reset, OAuth / social login, roles or permissions,
and request rate limiting. A public deployment must add a reverse-proxy rate
limit in front of these endpoints (noted in the README); this single-user
self-hosted PoC does not.
"""
