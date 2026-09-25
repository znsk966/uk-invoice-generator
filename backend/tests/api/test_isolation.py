"""Cross-user isolation: the heart of Phase 4.

Every domain query is scoped to the authenticated owner. Another user's data is
not merely forbidden — it is invisible: reads return 404 ``not_found`` (never
403), and lists are empty. Numbering is per owner, so two users legitimately
hold the same invoice number.
"""

from datetime import date

CLIENT_PAYLOAD = {
    "name": "Acme Ltd",
    "address_line1": "1 High Street",
    "city": "London",
    "postcode": "EC1A 1BB",
}
COMPANY_PAYLOAD = {
    "trading_name": "A's Freelance Co",
    "address_line1": "2 Baker Street",
    "city": "London",
    "postcode": "NW1 6XE",
    "vat_number": "GB123456789",
}
LINES = [
    {
        "position": 1,
        "description": "Consulting",
        "quantity": "2.000",
        "unit_price": "10.0000",
        "vat_rate_code": "standard",
    }
]


def _setup_and_issue(c) -> dict:
    """As user ``c``: create a profile + client + draft and issue it."""
    c.put("/api/v1/company-profile", json=COMPANY_PAYLOAD)
    client_id = c.post("/api/v1/clients", json=CLIENT_PAYLOAD).json()["id"]
    draft = c.post("/api/v1/invoices", json={"client_id": client_id, "lines": LINES}).json()
    issued = c.post(f"/api/v1/invoices/{draft['id']}/issue").json()
    return {"client_id": client_id, "draft_id": draft["id"], "issued": issued}


def test_lists_are_empty_for_a_fresh_second_user(login_as):
    a = login_as("a@example.com")
    _setup_and_issue(a)

    b = login_as("b@example.com")
    assert b.get("/api/v1/clients").json() == []
    assert b.get("/api/v1/invoices").json() == []


def test_second_user_cannot_read_or_mutate_first_users_invoice(login_as):
    a = login_as("a@example.com")
    state = _setup_and_issue(a)
    invoice_id = state["issued"]["id"]

    b = login_as("b@example.com")
    # Every verb on A's invoice is a 404 for B — existence must not leak.
    assert b.get(f"/api/v1/invoices/{invoice_id}").status_code == 404
    assert b.get(f"/api/v1/invoices/{invoice_id}/totals").status_code == 404
    assert (
        b.put(
            f"/api/v1/invoices/{invoice_id}",
            json={"client_id": state["client_id"], "lines": LINES},
        ).status_code
        == 404
    )
    assert b.delete(f"/api/v1/invoices/{invoice_id}").status_code == 404
    assert b.post(f"/api/v1/invoices/{invoice_id}/issue").status_code == 404
    assert b.post(f"/api/v1/invoices/{invoice_id}/void").status_code == 404


def test_second_user_cannot_read_first_users_client(login_as):
    a = login_as("a@example.com")
    state = _setup_and_issue(a)

    b = login_as("b@example.com")
    resp = b.get(f"/api/v1/clients/{state['client_id']}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found"


def test_second_user_has_no_company_profile_until_they_make_one(login_as):
    a = login_as("a@example.com")
    _setup_and_issue(a)

    b = login_as("b@example.com")
    missing = b.get("/api/v1/company-profile")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "company_profile_missing"

    # B creating their own profile does not touch A's.
    b.put("/api/v1/company-profile", json={**COMPANY_PAYLOAD, "trading_name": "B Co"})
    assert b.get("/api/v1/company-profile").json()["trading_name"] == "B Co"
    assert a.get("/api/v1/company-profile").json()["trading_name"] == "A's Freelance Co"


def test_numbering_is_independent_per_owner(login_as):
    year = date.today().year

    a = login_as("a@example.com")
    a_issued = _setup_and_issue(a)["issued"]
    assert a_issued["number"] == f"INV-{year}-00001"

    # A brand-new user issues their first invoice: same number, different owner.
    b = login_as("b@example.com")
    b_issued = _setup_and_issue(b)["issued"]
    assert b_issued["number"] == f"INV-{year}-00001"

    # A's next invoice continues A's own sequence, unaffected by B.
    a_client = a.post("/api/v1/clients", json=CLIENT_PAYLOAD).json()["id"]
    a_draft = a.post("/api/v1/invoices", json={"client_id": a_client, "lines": LINES}).json()
    a_second = a.post(f"/api/v1/invoices/{a_draft['id']}/issue").json()
    assert a_second["number"] == f"INV-{year}-00002"
