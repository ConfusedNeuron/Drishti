"""Smoke tests for the /api/research/events route."""
import json
import pytest
from fastapi.testclient import TestClient
from src.dashboard.app import app

client = TestClient(app)


def test_events_route_returns_503_when_artifact_missing(tmp_path, monkeypatch):
    """When the events_study.json artifact does not exist the route returns 503."""
    import src.dashboard.routes.research as research_mod
    monkeypatch.setattr(research_mod, "DATA_DIR", tmp_path)
    r = client.get("/api/research/events")
    assert r.status_code == 503
    detail = r.json()["detail"].lower()
    assert "artifact" in detail or "not built" in detail


def test_events_route_returns_payload_when_artifact_present(tmp_path, monkeypatch):
    """When the artifact exists the route returns its contents as JSON."""
    import src.dashboard.routes.research as research_mod
    monkeypatch.setattr(research_mod, "DATA_DIR", tmp_path)

    # Create the expected artifact path
    artifact_dir = tmp_path / "cache" / "research_artifacts_v2"
    artifact_dir.mkdir(parents=True)
    payload = {
        "episodes": [
            {"label": "COVID-19 Crash", "depth": -0.38, "cause": "Pandemic lockdown",
             "peak_date": "2020-01-14", "trough_date": "2020-03-23", "recovery_days": 175}
        ],
        "statistical_levels": {
            "median_fall": 0.22, "p75_fall": 0.32, "p90_fall": 0.38,
            "max_fall": 0.38, "note": "Based on 8 detected episodes."
        },
    }
    (artifact_dir / "events_study.json").write_text(json.dumps(payload))

    r = client.get("/api/research/events")
    assert r.status_code == 200
    data = r.json()
    assert "episodes" in data
    assert data["episodes"][0]["label"] == "COVID-19 Crash"
