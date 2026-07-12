"""GET /api/research/diagnostics returns the univariate + multivariate ladder."""
from fastapi.testclient import TestClient
from src.dashboard.app import app

client = TestClient(app)


def test_diagnostics_route_returns_both_sections():
    client.post("/api/portfolio/import/sample?sample_id=nifty-demo-2026")
    r = client.get("/api/research/diagnostics")
    assert r.status_code == 200
    d = r.json()
    assert set(d.keys()) >= {"univariate", "multivariate"}
    assert isinstance(d["univariate"], dict) and d["univariate"]
