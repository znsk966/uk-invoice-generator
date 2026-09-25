"""API tests for the product catalog: CRUD, owner scoping, identity
immutability (through the API and through raw SQL), and concurrent creates."""

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

PRODUCT_PAYLOAD = {
    "code": "CONS-1H",
    "description": "Consulting, per hour",
    "kind": "service",
    "vat_rate_code": "standard",
    "unit_price": "95.0000",
}


def _make_product(client, **overrides) -> dict:
    resp = client.post("/api/v1/products", json={**PRODUCT_PAYLOAD, **overrides})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def test_create_get_and_list(client):
    product = _make_product(client)
    assert product["code"] == "CONS-1H"
    assert product["kind"] == "service"
    assert product["vat_rate_code"] == "standard"
    # Money is a string on the wire, never a JSON number.
    assert product["unit_price"] == "95.0000"
    assert product["archived_at"] is None

    assert client.get(f"/api/v1/products/{product['id']}").json() == product
    assert [p["id"] for p in client.get("/api/v1/products").json()] == [product["id"]]


def test_list_filters_by_kind(client):
    service = _make_product(client)
    goods = _make_product(
        client, code="WIDGET", description="Widget", kind="goods", unit_price="4.5000"
    )
    assert [p["id"] for p in client.get("/api/v1/products?kind=goods").json()] == [goods["id"]]
    assert [p["id"] for p in client.get("/api/v1/products?kind=service").json()] == [service["id"]]


def test_archive_hides_from_default_list_and_unarchive_restores(client):
    product = _make_product(client)
    archived = client.post(f"/api/v1/products/{product['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None

    assert client.get("/api/v1/products").json() == []
    listed = client.get("/api/v1/products?include_archived=true").json()
    assert [p["id"] for p in listed] == [product["id"]]

    restored = client.post(f"/api/v1/products/{product['id']}/unarchive").json()
    assert restored["archived_at"] is None
    assert len(client.get("/api/v1/products").json()) == 1


def test_there_is_no_delete_route(client):
    product = _make_product(client)
    assert client.delete(f"/api/v1/products/{product['id']}").status_code == 405


def test_duplicate_code_for_same_owner_is_409(client):
    _make_product(client)
    resp = client.post("/api/v1/products", json={**PRODUCT_PAYLOAD, "description": "Other"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "product_code_taken"


def test_same_code_for_different_owners_is_fine(login_as):
    _make_product(login_as())
    _make_product(login_as())


@pytest.mark.parametrize(
    "overrides",
    [
        {"unit_price": "-0.01"},
        {"unit_price": "NaN"},
        {"code": "   "},
        {"description": ""},
        {"kind": "subscription"},
    ],
)
def test_invalid_create_is_422(client, overrides):
    resp = client.post("/api/v1/products", json={**PRODUCT_PAYLOAD, **overrides})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "validation_failed"


# --------------------------------------------------------------------------- #
# Owner scoping (rule 9): another user's product is 404, never 403
# --------------------------------------------------------------------------- #
def test_other_owner_cannot_see_patch_archive_or_link(login_as):
    alice = login_as()
    bob = login_as()
    product = _make_product(alice)
    pid = product["id"]

    assert bob.get("/api/v1/products").json() == []
    for resp in (
        bob.get(f"/api/v1/products/{pid}"),
        bob.patch(f"/api/v1/products/{pid}", json={"unit_price": "1.0000"}),
        bob.post(f"/api/v1/products/{pid}/archive"),
        bob.post(f"/api/v1/products/{pid}/unarchive"),
    ):
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "not_found"

    # Linking Alice's product onto Bob's invoice (or preview) is also 404.
    bob_client_id = bob.post(
        "/api/v1/clients",
        json={"name": "B", "address_line1": "1 St", "city": "X", "postcode": "AB1 2CD"},
    ).json()["id"]
    line = {"position": 1, "product_id": pid, "quantity": "1.000"}
    create = bob.post("/api/v1/invoices", json={"client_id": bob_client_id, "lines": [line]})
    assert create.status_code == 404
    assert create.json()["detail"]["code"] == "not_found"
    preview = bob.post("/api/v1/invoices/preview-totals", json={"lines": [line]})
    assert preview.status_code == 404

    # And none of that touched Alice's product.
    after = alice.get(f"/api/v1/products/{pid}").json()
    assert after["unit_price"] == "95.0000"
    assert after["archived_at"] is None


# --------------------------------------------------------------------------- #
# Identity immutability through the API
# --------------------------------------------------------------------------- #
def test_price_only_patch_is_200(client):
    product = _make_product(client)
    resp = client.patch(f"/api/v1/products/{product['id']}", json={"unit_price": "120.5000"})
    assert resp.status_code == 200
    assert resp.json()["unit_price"] == "120.5000"
    assert resp.json()["description"] == product["description"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", "Something else"),
        ("vat_rate_code", "zero"),
        ("code", "NEW-CODE"),
        ("kind", "goods"),
    ],
)
def test_patching_an_identity_field_is_409_product_immutable(client, field, value):
    product = _make_product(client)
    resp = client.patch(
        f"/api/v1/products/{product['id']}", json={"unit_price": "1.0000", field: value}
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "product_immutable"
    assert field in detail["message"]
    assert "archive this product and create a new one" in detail["message"]
    # Nothing changed — not even the price that rode along.
    assert client.get(f"/api/v1/products/{product['id']}").json() == product


@pytest.mark.parametrize(
    "body",
    [
        {"unit_price": "1.0000", "colour": "red"},  # unknown field
        {"archived_at": None, "unit_price": "1.0000"},  # not an identity field either
        {"unit_price": "-5"},
        {"unit_price": "abc"},
        {"unit_price": "Infinity"},
        {},
    ],
)
def test_unknown_field_or_bad_price_is_422_validation_failed(client, body):
    product = _make_product(client)
    resp = client.patch(f"/api/v1/products/{product['id']}", json=body)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "validation_failed"
    assert client.get(f"/api/v1/products/{product['id']}").json() == product


# --------------------------------------------------------------------------- #
# Identity immutability through raw SQL (bypassing the API)
# --------------------------------------------------------------------------- #
def _raw(engine, sql: str, **params) -> None:
    with engine.begin() as conn:
        conn.execute(text(sql), params)


@pytest.mark.parametrize(
    "assignment",
    [
        "description = 'hacked'",
        "vat_rate_code = 'zero'",
        "code = 'HACKED'",
        "kind = 'goods'",
    ],
)
def test_raw_sql_update_of_identity_raises(client, db_engine_for_test, assignment):
    product = _make_product(client)
    with pytest.raises(DBAPIError, match="identity is immutable"):
        _raw(
            db_engine_for_test, f"UPDATE product SET {assignment} WHERE id = :id", id=product["id"]
        )


def test_raw_sql_delete_of_product_raises(client, db_engine_for_test):
    # Unreferenced by any line, so this is the trigger (not the FK) refusing.
    product = _make_product(client)
    with pytest.raises(DBAPIError, match="cannot be deleted"):
        _raw(db_engine_for_test, "DELETE FROM product WHERE id = :id", id=product["id"])


def test_raw_sql_update_of_price_and_archive_succeeds(client, db_engine_for_test):
    product = _make_product(client)
    _raw(
        db_engine_for_test,
        "UPDATE product SET unit_price = 1.2345, archived_at = now() WHERE id = :id",
        id=product["id"],
    )
    after = client.get(f"/api/v1/products/{product['id']}").json()
    assert after["unit_price"] == "1.2345"
    assert after["archived_at"] is not None


# --------------------------------------------------------------------------- #
# Concurrency
# --------------------------------------------------------------------------- #
def test_concurrent_creates_with_same_code_are_201_and_409(app, client, monkeypatch):
    """Two simultaneous creates of one code: one 201, one 409 — never a 500.

    The duplicate pre-check is patched to wait at a barrier and report "no
    duplicate", so both requests are guaranteed to reach the INSERT and the
    loser is caught by the unique constraint (the savepoint path), not the fast
    path.
    """
    from app.modules.products import service

    barrier = threading.Barrier(2, timeout=30)

    def _both_pass_the_precheck(*_args) -> bool:
        barrier.wait()
        return False

    monkeypatch.setattr(service, "_code_exists", _both_pass_the_precheck)

    codes: list[int] = []
    lock = threading.Lock()

    def _create() -> None:
        with TestClient(app, cookies=client.cookies) as racer:
            resp = racer.post("/api/v1/products", json=PRODUCT_PAYLOAD)
        with lock:
            codes.append(resp.status_code)
            if resp.status_code == 409:
                assert resp.json()["detail"]["code"] == "product_code_taken"

    threads = [threading.Thread(target=_create) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(codes) == [201, 409]
    assert len(client.get("/api/v1/products").json()) == 1
