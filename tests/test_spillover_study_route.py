"""Smoke tests for the /api/research/spillover/study route."""
import json
import pytest
from fastapi.testclient import TestClient
from src.dashboard.app import app

client = TestClient(app)


def test_spillover_study_route_returns_503_when_artifact_missing(tmp_path, monkeypatch):
    """When the spillover_study.json artifact does not exist the route returns 503."""
    import src.dashboard.routes.research as research_mod
    monkeypatch.setattr(research_mod, "DATA_DIR", tmp_path)
    r = client.get("/api/research/spillover/study")
    assert r.status_code == 503
    detail = r.json()["detail"].lower()
    assert "artifact" in detail or "not built" in detail


def test_spillover_study_route_returns_payload_when_artifact_present(tmp_path, monkeypatch):
    """When the artifact exists the route returns its contents as JSON."""
    import src.dashboard.routes.research as research_mod
    monkeypatch.setattr(research_mod, "DATA_DIR", tmp_path)

    # Create the expected artifact path
    artifact_dir = tmp_path / "cache" / "research_artifacts_v2"
    artifact_dir.mkdir(parents=True)
    payload = {
        "panels": {
            "large": {"total_spillover": 62.4, "net_spillover": {"NIFTY": 5.1}},
            "mid": {"total_spillover": 58.1, "net_spillover": {"NSEMD150": -2.3}},
            "combined": {"total_spillover": 60.7, "net_spillover": {}},
        }
    }
    (artifact_dir / "spillover_study.json").write_text(json.dumps(payload))

    r = client.get("/api/research/spillover/study")
    assert r.status_code == 200
    data = r.json()
    assert "panels" in data
    assert set(data["panels"].keys()) == {"large", "mid", "combined"}
    assert data["panels"]["large"]["total_spillover"] == pytest.approx(62.4)
