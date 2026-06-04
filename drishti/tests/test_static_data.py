import pytest
from httpx import AsyncClient, ASGITransport
from src.dashboard.app import app


@pytest.mark.asyncio
async def test_static_data_schema():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/static-data")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"regime", "regime_prob", "dy_total", "ic_signals", "var_range", "data_as_of"}


@pytest.mark.asyncio
async def test_static_data_nulls_gracefully(tmp_path, monkeypatch):
    import src.bloomberg.cache as cache_mod
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path / "bloomberg")
    import src.dashboard.routes.static_data as sd
    sd._load.cache_clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/static-data")
    assert r.status_code == 200
    data = r.json()
    assert data["data_as_of"] is None
