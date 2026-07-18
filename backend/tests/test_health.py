import httpx
import pytest

from app import main
from app.main import create_app


async def _get_health(monkeypatch, db_ok: bool):
    monkeypatch.setattr(main, "check_db", lambda: db_ok)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health")


@pytest.mark.anyio
async def test_health_database_ok(monkeypatch):
    resp = await _get_health(monkeypatch, db_ok=True)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


@pytest.mark.anyio
async def test_health_database_unavailable(monkeypatch):
    # The app must still respond 200 with status "ok" even when the DB is down.
    resp = await _get_health(monkeypatch, db_ok=False)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "unavailable"}


@pytest.fixture
def anyio_backend():
    return "asyncio"
