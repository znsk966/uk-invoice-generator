"""API tests for the invoice lifecycle: drafts, totals, issue, void,
immutability, gapless numbering, archived clients, and tax-point rates."""

from datetime import date

import pytest
from sqlalchemy import text

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
    "vat_number": "GB123456789",
}
DEFAULT_LINES = [
    {
        "position": 1,
        "description": "Consulting",
        "quantity": "2.000",
        "unit_price": "10.0000",
        "vat_rate_code": "standard",
    }
]


def _make_client(client, **overrides) -> int:
    return client.post("/api/v1/clients", json={**CLIENT_PAYLOAD, **overrides}).json()["id"]


def _make_company(client) -> None:
    client.put("/api/v1/company-profile", json=COMPANY_PAYLOAD)


def _make_draft(client, client_id, lines=None) -> dict:
    payload = {"client_id": client_id, "lines": lines if lines is not None else DEFAULT_LINES}
    resp = client.post("/api/v1/invoices", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _current_year() -> int:
    return date.today().year


# --------------------------------------------------------------------------- #
# Full lifecycle
# --------------------------------------------------------------------------- #
def test_full_lifecycle(client, db_engine_for_test):
    _make_company(client)
    client_id = _make_client(client)
    draft = _make_draft(client, client_id)
    assert draft["status"] == "draft"
    assert draft["number"] is None
    assert draft["snapshot"] is None

    # Totals endpoint computes on demand (money as strings).
    totals = client.get(f"/api/v1/invoices/{draft['id']}/totals").json()
    assert totals["total_net"] == "20.00"
    assert totals["total_vat"] == "4.00"
    assert totals["total_gross"] == "24.00"
    assert totals["groups"][0]["code"] == "standard"
    assert totals["groups"][0]["vat"] == "4.00"

    # Issue.
    issued = client.post(f"/api/v1/invoices/{draft['id']}/issue").json()
    assert issued["status"] == "issued"
    assert issued["number"] == f"INV-{_current_year()}-00001"
    assert issued["invoice_date"] is not None

    # GET serves money from the snapshot, never recomputed.
    got = client.get(f"/api/v1/invoices/{draft['id']}").json()
    snap = got["snapshot"]
    assert snap["number"] == f"INV-{_current_year()}-00001"
    assert snap["totals"] == {"net": "20.00", "vat": "4.00", "gross": "24.00"}
    assert snap["seller"]["trading_name"] == "My Freelance Co"
    assert snap["client"]["name"] == "Acme Ltd"
    assert snap["lines"][0]["line_net"] == "20.00"
    assert snap["lines"][0]["rate"] == "0.2000"

    # Void keeps the number and the snapshot.
    voided = client.post(f"/api/v1/invoices/{draft['id']}/void").json()
    assert voided["status"] == "void"
    assert voided["number"] == f"INV-{_current_year()}-00001"
    assert voided["snapshot"]["totals"] == {"net": "20.00", "vat": "4.00", "gross": "24.00"}


# --------------------------------------------------------------------------- #
# Immutability at the API level
# --------------------------------------------------------------------------- #
def _issue_one(client) -> dict:
    _make_company(client)
    client_id = _make_client(client)
    draft = _make_draft(client, client_id)
    return client.post(f"/api/v1/invoices/{draft['id']}/issue").json()


def test_editing_issued_invoice_is_409(client):
    issued = _issue_one(client)
    resp = client.put(
        f"/api/v1/invoices/{issued['id']}",
        json={"client_id": issued["client_id"], "lines": DEFAULT_LINES},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "invoice_not_draft"


def test_deleting_issued_invoice_is_409(client):
    issued = _issue_one(client)
    resp = client.delete(f"/api/v1/invoices/{issued['id']}")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "invoice_not_draft"


def test_issuing_twice_is_409(client):
    issued = _issue_one(client)
    resp = client.post(f"/api/v1/invoices/{issued['id']}/issue")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "invoice_not_draft"


def test_deleting_a_draft_succeeds(client):
    client_id = _make_client(client)
    draft = _make_draft(client, client_id)
    resp = client.delete(f"/api/v1/invoices/{draft['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/v1/invoices/{draft['id']}").status_code == 404


def test_immutability_trigger_fires_on_direct_line_update(client, db_engine_for_test):
    """Bypass the API entirely: a raw SQL UPDATE of an issued invoice's line must
    be rejected by the DB trigger (defense in depth)."""
    issued = _issue_one(client)
    with pytest.raises(Exception) as excinfo:  # noqa: PT011 - DB driver error type
        with db_engine_for_test.begin() as conn:
            conn.execute(
                text("UPDATE invoice_line SET description = 'hacked' WHERE invoice_id = :id"),
                {"id": issued["id"]},
            )
    assert "immutable" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# Gapless numbering
# --------------------------------------------------------------------------- #
def test_two_issues_are_sequential(client):
    _make_company(client)
    client_id = _make_client(client)
    first = client.post(f"/api/v1/invoices/{_make_draft(client, client_id)['id']}/issue").json()
    second = client.post(f"/api/v1/invoices/{_make_draft(client, client_id)['id']}/issue").json()
    assert first["number"] == f"INV-{_current_year()}-00001"
    assert second["number"] == f"INV-{_current_year()}-00002"


def test_failed_issue_does_not_burn_a_number(client):
    _make_company(client)
    # A draft whose client gets archived before issue: the issue fails.
    doomed_client = _make_client(client, name="Doomed")
    doomed_draft = _make_draft(client, doomed_client)
    client.post(f"/api/v1/clients/{doomed_client}/archive")
    failed = client.post(f"/api/v1/invoices/{doomed_draft['id']}/issue")
    assert failed.status_code == 409
    assert failed.json()["detail"]["code"] == "client_archived"

    # The next successful issue still gets 00001 — the number was not burned.
    good_client = _make_client(client, name="Good")
    good_draft = _make_draft(client, good_client)
    issued = client.post(f"/api/v1/invoices/{good_draft['id']}/issue").json()
    assert issued["number"] == f"INV-{_current_year()}-00001"


# --------------------------------------------------------------------------- #
# Archived clients
# --------------------------------------------------------------------------- #
def test_archived_client_blocks_new_invoice_but_old_stays_readable(client):
    _make_company(client)
    client_id = _make_client(client)
    draft = _make_draft(client, client_id)
    issued = client.post(f"/api/v1/invoices/{draft['id']}/issue").json()

    client.post(f"/api/v1/clients/{client_id}/archive")

    # New invoice for the archived client is refused.
    blocked = client.post("/api/v1/invoices", json={"client_id": client_id, "lines": DEFAULT_LINES})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "client_archived"

    # The previously issued invoice is still fully readable from its snapshot.
    still = client.get(f"/api/v1/invoices/{issued['id']}")
    assert still.status_code == 200
    assert still.json()["snapshot"]["client"]["name"] == "Acme Ltd"


# --------------------------------------------------------------------------- #
# Rates at the tax point
# --------------------------------------------------------------------------- #
def test_tax_point_before_seed_date_is_422(client):
    _make_company(client)
    client_id = _make_client(client)
    draft = _make_draft(client, client_id)
    resp = client.post(
        f"/api/v1/invoices/{draft['id']}/issue",
        json={"tax_point_date": "2011-01-03"},  # before the seed's 2011-01-04
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "validation_failed"


# --------------------------------------------------------------------------- #
# Float in JSON parses exactly; snapshot money is stored as JSON strings
# --------------------------------------------------------------------------- #
def test_float_in_json_parses_exactly_and_snapshot_stores_strings(client, db_engine_for_test):
    _make_company(client)
    client_id = _make_client(client)
    # unit_price sent as a JSON *number* (float), not a string.
    lines = [
        {
            "position": 1,
            "description": "Consulting",
            "quantity": 2,
            "unit_price": 10.10,
            "vat_rate_code": "standard",
        }
    ]
    draft = _make_draft(client, client_id, lines=lines)
    issued = client.post(f"/api/v1/invoices/{draft['id']}/issue").json()

    snap = issued["snapshot"]
    # Parsed exactly (not 10.0999...), stored at Numeric(12,4) precision.
    assert snap["lines"][0]["unit_price"] == "10.1000"
    assert isinstance(snap["lines"][0]["unit_price"], str)
    # 2 * 10.10 = 20.20 net; 20% VAT = 4.04.
    assert snap["totals"] == {"net": "20.20", "vat": "4.04", "gross": "24.24"}

    # In the stored JSONB, money is a JSON string, never a JSON number.
    with db_engine_for_test.connect() as conn:
        typ = conn.execute(
            text("SELECT jsonb_typeof(snapshot->'totals'->'net') FROM invoice WHERE id = :id"),
            {"id": issued["id"]},
        ).scalar()
    assert typ == "string"
