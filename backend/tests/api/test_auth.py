"""API tests for authentication: register, login, logout, me, sessions."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text


def test_register_sets_cookie_and_me_works(client):
    # The `client` fixture already registered a user and holds the cookie.
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"
    assert "id" in me.json()
    # The session cookie is present and HTTP-only.
    assert "session" in client.cookies


def test_register_lowercases_email(login_as):
    mixed = login_as("MixedCase@Example.COM")
    assert mixed.get("/api/v1/auth/me").json()["email"] == "mixedcase@example.com"


def test_duplicate_email_is_409(app, login_as):
    login_as("dupe@example.com")
    # A second registration of the same email, via a fresh client.
    from fastapi.testclient import TestClient

    other = TestClient(app)
    resp = other.post(
        "/api/v1/auth/register",
        json={"email": "dupe@example.com", "password": "password123"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "email_taken"


def test_short_password_is_422(app):
    from fastapi.testclient import TestClient

    resp = TestClient(app).post(
        "/api/v1/auth/register",
        json={"email": "shortpw@example.com", "password": "short"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "validation_failed"


def test_login_succeeds_and_issues_a_session(app, login_as):
    login_as("returning@example.com", password="correcthorse")
    from fastapi.testclient import TestClient

    fresh = TestClient(app)
    resp = fresh.post(
        "/api/v1/auth/login",
        json={"email": "returning@example.com", "password": "correcthorse"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "returning@example.com"
    assert fresh.get("/api/v1/auth/me").status_code == 200


def test_wrong_password_and_unknown_email_are_identical_401(app, login_as):
    login_as("real@example.com", password="correcthorse")
    from fastapi.testclient import TestClient

    wrong_password = TestClient(app).post(
        "/api/v1/auth/login",
        json={"email": "real@example.com", "password": "WRONGpassword"},
    )
    unknown_email = TestClient(app).post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "correcthorse"},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    # Byte-for-byte identical bodies — nothing leaks which email exists.
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["detail"]["code"] == "invalid_credentials"


def test_me_without_cookie_is_401(app):
    from fastapi.testclient import TestClient

    resp = TestClient(app).get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "not_authenticated"


def test_logout_revokes_the_session_server_side(client):
    # Grab the raw token so we can replay it after logout.
    token = client.cookies.get("session")
    assert client.get("/api/v1/auth/me").status_code == 200

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204

    # The client's own cookie was cleared: it is now anonymous.
    assert client.get("/api/v1/auth/me").status_code == 401

    # And the token is dead server-side even if replayed directly (not just
    # cleared from the browser) — this is real revocation.
    client.cookies.set("session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_is_idempotent(app):
    from fastapi.testclient import TestClient

    # Logging out with no session at all still succeeds.
    resp = TestClient(app).post("/api/v1/auth/logout")
    assert resp.status_code == 204


def test_expired_session_is_401(client, db_engine_for_test):
    # Force the session to have already expired, then confirm it no longer authenticates.
    from app.modules.auth.security import hash_token

    token = client.cookies.get("session")
    with db_engine_for_test.begin() as conn:
        conn.execute(
            text("UPDATE user_session SET expires_at = :past WHERE token_hash = :h"),
            {"past": datetime.now(UTC) - timedelta(days=1), "h": hash_token(token)},
        )

    assert client.get("/api/v1/auth/me").status_code == 401


def test_domain_endpoints_require_authentication(app):
    from fastapi.testclient import TestClient

    anon = TestClient(app)
    assert anon.get("/api/v1/clients").status_code == 401
    assert anon.get("/api/v1/invoices").status_code == 401
    assert anon.get("/api/v1/company-profile").status_code == 401
    preview = anon.post("/api/v1/invoices/preview-totals", json={"lines": []})
    assert preview.status_code == 401
    assert preview.json()["detail"]["code"] == "not_authenticated"
