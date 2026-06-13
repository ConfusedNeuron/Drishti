"""Smoke tests for the /api/research/regimes-study route."""
import json
import pytest
from fastapi.testclient import TestClient
from src.dashboard.app import app

client = TestClient(app)


def test_regimes_study_route_returns_503_when_artifact_missing(tmp_path, monkeypatch):
    """When the regime_study.json artifact does not exist the route returns 503."""
    import src.dashboard.routes.research as research_mod
    monkeypatch.setattr(research_mod, "DATA_DIR", tmp_path)
    r = client.get("/api/research/regimes-study")
    assert r.status_code == 503
    detail = r.json()["detail"].lower()
    assert "artifact" in detail or "not built" in detail


def test_regimes_study_route_returns_payload_when_artifact_present(tmp_path, monkeypatch):
    """When the artifact exists the route returns its contents as JSON."""
    import src.dashboard.routes.research as research_mod
    monkeypatch.setattr(research_mod, "DATA_DIR", tmp_path)

    # Create the expected artifact path
    artifact_dir = tmp_path / "cache" / "research_artifacts_v2"
    artifact_dir.mkdir(parents=True)
    payload = {
        "regime_series": [],
        "regime_signs": {},
        "hmm_prob": [],
        "current_state": {},
        "bull_bear_episodes": [],
    }
    (artifact_dir / "regime_study.json").write_text(json.dumps(payload))

    r = client.get("/api/research/regimes-study")
    assert r.status_code == 200
    data = r.json()
    assert data["regime_series"] == []
    assert data["hmm_prob"] == []
