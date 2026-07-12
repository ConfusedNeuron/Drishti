"""/api/copilot/ask must label its answer mode truthfully."""
from fastapi.testclient import TestClient
from src.dashboard.app import app

client = TestClient(app)


def _load_sample():
    r = client.post("/api/portfolio/import/sample?sample_id=nifty-demo-2026")
    assert r.status_code == 200


def test_advice_refused_even_without_llm_key(monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "llm_api_key", None)
    _load_sample()
    r = client.post("/api/copilot/ask", json={"question": "should I buy more RELIANCE?"})
    assert r.status_code == 200
    d = r.json()
    assert d["source"] == "safety_filter"
    assert d["advice_refused"] is True


def test_no_key_falls_back_to_memo(monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "llm_api_key", None)
    _load_sample()
    r = client.post("/api/copilot/ask", json={"question": "explain my VaR"})
    d = r.json()
    assert d["source"] == "deterministic_memo"


def test_llm_exception_labeled_llm_error(monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "sk-fake-key")
    import anthropic

    class Boom:
        def __init__(self, api_key): pass
        class messages:
            @staticmethod
            def create(**kw): raise RuntimeError("network down")

    monkeypatch.setattr(anthropic, "Anthropic", Boom)
    _load_sample()
    r = client.post("/api/copilot/ask", json={"question": "explain my VaR"})
    d = r.json()
    assert d["source"] == "llm_error"
