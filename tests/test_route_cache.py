"""TTL cache unit tests + regime endpoint memoization."""
import time
from fastapi.testclient import TestClient
from src.dashboard.app import app
from src.dashboard import route_cache

client = TestClient(app)


def test_put_get_roundtrip():
    route_cache.clear()
    route_cache.put(("k",), {"a": 1})
    assert route_cache.get(("k",)) == {"a": 1}


def test_expiry(monkeypatch):
    route_cache.clear()
    route_cache.put(("k",), "v")
    real = time.time()
    monkeypatch.setattr(time, "time", lambda: real + 7200)
    assert route_cache.get(("k",), max_age_s=3600) is None


def test_regime_endpoint_computes_once(monkeypatch):
    route_cache.clear()
    client.post("/api/portfolio/import/sample?sample_id=nifty-demo-2026")
    import src.research.hmm as hmm_mod
    calls = {"n": 0}
    real_wf = hmm_mod.walk_forward_hmm

    def counting(*a, **kw):
        calls["n"] += 1
        return real_wf(*a, **kw)

    monkeypatch.setattr(hmm_mod, "walk_forward_hmm", counting)
    assert client.get("/api/research/regime").status_code == 200
    assert client.get("/api/research/regime").status_code == 200
    assert calls["n"] == 1
