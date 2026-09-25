"""API tests for invoice lines linked to catalog products: server authority,
archived products, price independence, snapshot v2, ad-hoc line validation, and
the linked-line integrity trigger probed through raw SQL."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

CLIENT_PAYLOAD = {
    "name": "Acme Ltd",
    "address_line1": "1 High Street",
    "city": "London",
    "postcode": "EC1A 1BB",
}
COMPANY_PAYLOAD = {
    "trading_name": "My Freelance Co",
    "address_line1": "2 Baker Street",
    "city": "London",
    "postcode": "NW1 6XE",
}
SERVICE = {
    "code": "CONS-1H",
    "description": "Consulting, per hour",
    "kind": "service",
    "vat_rate_code": "standard",
    "unit_price": "10.0000",
}
GOODS = {
    "code": "BOOK",
    "description": "Printed handbook",
    "kind": "goods",
    "vat_rate_code": "zero",
    "unit_price": "25.0000",
}
AD_HOC = {
    "position": 2,
    "description": "Travel",
    "quantity": "1.000",
    "unit_price": "5.0000",
    "vat_rate_code": "exempt",
}


def _make_product(client, payload=SERVICE) -> dict:
    resp = client.post("/api/v1/products", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_client(client) -> int:
    return client.post("/api/v1/clients", json=CLIENT_PAYLOAD).json()["id"]


def _catalog_line(product_id: int, position: int = 1, **extra) -> dict:
    return {"position": position, "product_id": product_id, "quantity": "2.000", **extra}


def _create(client, client_id: int, lines: list[dict]):
    return client.post("/api/v1/invoices", json={"client_id": client_id, "lines": lines})


# --------------------------------------------------------------------------- #
# Server authority
# --------------------------------------------------------------------------- #
def test_linked_line_takes_description_and_vat_from_product(client):
    product = _make_product(client)
    resp = _create(
        client,
        _make_client(client),
        [_catalog_line(product["id"], description="Something I typed", vat_rate_code="zero")],
    )
    assert resp.status_code == 201, resp.text
    line = resp.json()["lines"][0]
    assert line["product_id"] == product["id"]
    assert line["description"] == "Consulting, per hour"
    assert line["vat_rate_code"] == "standard"


def test_linked_line_price_defaults_to_product_price_but_request_wins(client):
    product = _make_product(client)
    client_id = _make_client(client)
    defaulted = _create(client, client_id, [_catalog_line(product["id"])]).json()
    assert defaulted["lines"][0]["unit_price"] == "10.0000"

    overridden = _create(
        client, client_id, [_catalog_line(product["id"], unit_price="7.5000")]
    ).json()
    assert overridden["lines"][0]["unit_price"] == "7.5000"


def test_preview_takes_vat_from_product_not_body(client):
    # The product is standard-rated; the body claims zero. Server must use 20%.
    product = _make_product(client)
    resp = client.post(
        "/api/v1/invoices/preview-totals",
        json={"lines": [_catalog_line(product["id"], unit_price="10.0000", vat_rate_code="zero")]},
    )
    assert resp.status_code == 200, resp.text
    totals = resp.json()
    assert [g["code"] for g in totals["groups"]] == ["standard"]
    assert totals["total_net"] == "20.00"
    assert totals["total_vat"] == "4.00"


def test_put_also_applies_server_authority(client):
    product = _make_product(client)
    client_id = _make_client(client)
    draft = _create(client, client_id, [AD_HOC]).json()
    resp = client.put(
        f"/api/v1/invoices/{draft['id']}",
        json={
            "client_id": client_id,
            "lines": [_catalog_line(product["id"], description="nope", vat_rate_code="reduced")],
        },
    )
    assert resp.status_code == 200, resp.text
    line = resp.json()["lines"][0]
    assert (line["description"], line["vat_rate_code"]) == ("Consulting, per hour", "standard")


def test_unknown_product_is_404(client):
    resp = _create(client, _make_client(client), [_catalog_line(999_999)])
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found"


# --------------------------------------------------------------------------- #
# Ad-hoc lines keep working, and must be complete
# --------------------------------------------------------------------------- #
def test_ad_hoc_and_catalog_lines_mix(client):
    product = _make_product(client)
    resp = _create(client, _make_client(client), [_catalog_line(product["id"]), AD_HOC])
    assert resp.status_code == 201, resp.text
    lines = resp.json()["lines"]
    assert lines[0]["product_id"] == product["id"]
    assert lines[1]["product_id"] is None
    assert lines[1]["description"] == "Travel"
    assert lines[1]["vat_rate_code"] == "exempt"


@pytest.mark.parametrize(
    ("missing", "replacement"),
    [
        ("description", None),
        ("description", "   "),
        ("vat_rate_code", None),
        ("unit_price", None),
    ],
)
def test_incomplete_ad_hoc_line_is_422(client, missing, replacement):
    line = {**AD_HOC, "position": 1}
    if replacement is None:
        del line[missing]
    else:
        line[missing] = replacement
    for resp in (
        _create(client, _make_client(client), [line]),
        client.post("/api/v1/invoices/preview-totals", json={"lines": [line]}),
    ):
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["code"] == "validation_failed"
        assert missing in str(detail["errors"])


# --------------------------------------------------------------------------- #
# Archived products
# --------------------------------------------------------------------------- #
def test_newly_adding_an_archived_product_is_409(client):
    product = _make_product(client)
    client.post(f"/api/v1/products/{product['id']}/archive")
    resp = _create(client, _make_client(client), [_catalog_line(product["id"])])
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "product_archived"


def test_resaving_a_draft_that_already_links_an_archived_product_is_200(client):
    product = _make_product(client)
    client_id = _make_client(client)
    draft = _create(client, client_id, [_catalog_line(product["id"])]).json()
    client.post(f"/api/v1/products/{product['id']}/archive")

    body = {"client_id": client_id, "notes": "edited", "lines": [_catalog_line(product["id"])]}
    resp = client.put(f"/api/v1/invoices/{draft['id']}", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json()["lines"][0]["product_id"] == product["id"]

    # The preview keeps working for that draft too.
    preview = client.post("/api/v1/invoices/preview-totals", json={"lines": body["lines"]})
    assert preview.status_code == 200


def test_adding_an_archived_product_to_an_existing_draft_is_409(client):
    product = _make_product(client)
    client.post(f"/api/v1/products/{product['id']}/archive")
    client_id = _make_client(client)
    draft = _create(client, client_id, [AD_HOC]).json()
    resp = client.put(
        f"/api/v1/invoices/{draft['id']}",
        json={"client_id": client_id, "lines": [AD_HOC, _catalog_line(product["id"])]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "product_archived"


# --------------------------------------------------------------------------- #
# Price independence
# --------------------------------------------------------------------------- #
def test_product_price_change_never_touches_existing_lines(client):
    client.put("/api/v1/company-profile", json=COMPANY_PAYLOAD)
    product = _make_product(client)
    draft = _create(client, _make_client(client), [_catalog_line(product["id"])]).json()
    assert draft["lines"][0]["unit_price"] == "10.0000"

    patched = client.patch(f"/api/v1/products/{product['id']}", json={"unit_price": "99.0000"})
    assert patched.status_code == 200

    line = client.get(f"/api/v1/invoices/{draft['id']}").json()["lines"][0]
    assert line["unit_price"] == "10.0000"

    # Preview with the line as the editor holds it uses the line's price.
    preview = client.post(
        "/api/v1/invoices/preview-totals",
        json={"lines": [_catalog_line(product["id"], unit_price=line["unit_price"])]},
    ).json()
    assert preview["total_net"] == "20.00"

    # So do the draft totals and the issued snapshot.
    assert client.get(f"/api/v1/invoices/{draft['id']}/totals").json()["total_net"] == "20.00"
    issued = client.post(f"/api/v1/invoices/{draft['id']}/issue").json()
    assert issued["snapshot"]["lines"][0]["unit_price"] == "10.0000"
    assert issued["snapshot"]["totals"] == {"net": "20.00", "vat": "4.00", "gross": "24.00"}


# --------------------------------------------------------------------------- #
# Snapshot v2
# --------------------------------------------------------------------------- #
def test_snapshot_v2_carries_product_fields_and_nulls_for_ad_hoc(client):
    client.put("/api/v1/company-profile", json=COMPANY_PAYLOAD)
    goods = _make_product(client, GOODS)
    draft = _create(client, _make_client(client), [_catalog_line(goods["id"]), AD_HOC]).json()
    snapshot = client.post(f"/api/v1/invoices/{draft['id']}/issue").json()["snapshot"]

    assert snapshot["version"] == 2
    catalog, ad_hoc = snapshot["lines"]
    assert catalog["product_id"] == goods["id"]
    assert catalog["product_code"] == "BOOK"
    assert catalog["kind"] == "goods"
    assert catalog["description"] == "Printed handbook"
    assert catalog["vat_rate_code"] == "zero"
    assert ad_hoc["product_id"] is None
    assert ad_hoc["product_code"] is None
    assert ad_hoc["kind"] is None


# --------------------------------------------------------------------------- #
# Linked-line integrity through raw SQL (bypassing the API)
# --------------------------------------------------------------------------- #
def _insert_line(engine, invoice_id: int, product_id: int, description: str, vat: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO invoice_line (invoice_id, position, product_id, description, "
                "quantity, unit_price, vat_rate_code) "
                "VALUES (:inv, 50, :pid, :desc, 1, 1, :vat)"
            ),
            {"inv": invoice_id, "pid": product_id, "desc": description, "vat": vat},
        )


def test_raw_linked_line_with_matching_fields_is_accepted(client, db_engine_for_test):
    product = _make_product(client)
    draft = _create(client, _make_client(client), [AD_HOC]).json()
    _insert_line(db_engine_for_test, draft["id"], product["id"], SERVICE["description"], "standard")


def test_raw_linked_line_with_mismatched_description_raises(client, db_engine_for_test):
    product = _make_product(client)
    draft = _create(client, _make_client(client), [AD_HOC]).json()
    with pytest.raises(DBAPIError, match="description must equal product"):
        _insert_line(db_engine_for_test, draft["id"], product["id"], "Tampered", "standard")


def test_raw_linked_line_with_mismatched_vat_raises(client, db_engine_for_test):
    product = _make_product(client)
    draft = _create(client, _make_client(client), [AD_HOC]).json()
    with pytest.raises(DBAPIError, match="vat_rate_code must equal product"):
        _insert_line(db_engine_for_test, draft["id"], product["id"], SERVICE["description"], "zero")


def test_raw_linked_line_to_another_owners_product_raises(login_as, db_engine_for_test):
    alice = login_as()
    bob = login_as()
    bobs_product = _make_product(bob)
    alices_draft = _create(alice, _make_client(alice), [AD_HOC]).json()
    with pytest.raises(DBAPIError, match="owned by another user"):
        _insert_line(
            db_engine_for_test,
            alices_draft["id"],
            bobs_product["id"],
            SERVICE["description"],
            "standard",
        )


def test_raw_update_of_a_linked_draft_line_description_raises(client, db_engine_for_test):
    product = _make_product(client)
    draft = _create(client, _make_client(client), [_catalog_line(product["id"])]).json()
    with pytest.raises(DBAPIError, match="description must equal product"):
        with db_engine_for_test.begin() as conn:
            conn.execute(
                text("UPDATE invoice_line SET description = 'x' WHERE invoice_id = :id"),
                {"id": draft["id"]},
            )


def test_both_line_triggers_coexist_immutability_fires_first(client, db_engine_for_test):
    """A linked line on an issued invoice: the update below would violate *both*
    triggers. Alphabetical firing order means the immutability guard answers."""
    client.put("/api/v1/company-profile", json=COMPANY_PAYLOAD)
    product = _make_product(client)
    draft = _create(client, _make_client(client), [_catalog_line(product["id"])]).json()
    client.post(f"/api/v1/invoices/{draft['id']}/issue")
    with pytest.raises(DBAPIError, match="immutable"):
        with db_engine_for_test.begin() as conn:
            conn.execute(
                text("UPDATE invoice_line SET description = 'x' WHERE invoice_id = :id"),
                {"id": draft["id"]},
            )


def test_referenced_product_cannot_be_deleted_either(client, db_engine_for_test):
    product = _make_product(client)
    _create(client, _make_client(client), [_catalog_line(product["id"])])
    with pytest.raises(DBAPIError):
        with db_engine_for_test.begin() as conn:
            conn.execute(text("DELETE FROM product WHERE id = :id"), {"id": product["id"]})
