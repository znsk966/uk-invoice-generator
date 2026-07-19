"""API tests for clients and company profile."""

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


def test_create_and_get_client(client):
    resp = client.post("/api/v1/clients", json=CLIENT_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Acme Ltd"
    assert body["country"] == "GB"  # default
    assert body["archived_at"] is None

    got = client.get(f"/api/v1/clients/{body['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


def test_get_missing_client_is_404_with_code(client):
    resp = client.get("/api/v1/clients/999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found"


def test_list_excludes_archived_by_default(client):
    a = client.post("/api/v1/clients", json=CLIENT_PAYLOAD).json()
    client.post("/api/v1/clients", json={**CLIENT_PAYLOAD, "name": "Beta"}).json()
    client.post(f"/api/v1/clients/{a['id']}/archive")

    default = client.get("/api/v1/clients").json()
    assert {c["name"] for c in default} == {"Beta"}

    included = client.get("/api/v1/clients", params={"include_archived": True}).json()
    assert {c["name"] for c in included} == {"Acme Ltd", "Beta"}


def test_archive_then_unarchive(client):
    c = client.post("/api/v1/clients", json=CLIENT_PAYLOAD).json()
    archived = client.post(f"/api/v1/clients/{c['id']}/archive").json()
    assert archived["archived_at"] is not None
    unarchived = client.post(f"/api/v1/clients/{c['id']}/unarchive").json()
    assert unarchived["archived_at"] is None


def test_update_client_full_replace(client):
    c = client.post("/api/v1/clients", json=CLIENT_PAYLOAD).json()
    resp = client.put(
        f"/api/v1/clients/{c['id']}",
        json={**CLIENT_PAYLOAD, "name": "Renamed", "city": "Leeds"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["city"] == "Leeds"


def test_no_delete_route_for_clients(client):
    c = client.post("/api/v1/clients", json=CLIENT_PAYLOAD).json()
    resp = client.delete(f"/api/v1/clients/{c['id']}")
    # There is deliberately no DELETE handler — the router only allows archive.
    assert resp.status_code == 405


def test_company_profile_missing_is_404_with_code(client):
    resp = client.get("/api/v1/company-profile")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "company_profile_missing"


def test_company_profile_upsert_creates_then_updates(client):
    created = client.put("/api/v1/company-profile", json=COMPANY_PAYLOAD)
    assert created.status_code == 200
    assert created.json()["id"] == 1
    assert created.json()["trading_name"] == "My Freelance Co"

    updated = client.put(
        "/api/v1/company-profile",
        json={**COMPANY_PAYLOAD, "trading_name": "Renamed Co"},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == 1  # still the singleton
    assert updated.json()["trading_name"] == "Renamed Co"

    assert client.get("/api/v1/company-profile").json()["trading_name"] == "Renamed Co"
