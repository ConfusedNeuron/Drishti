import importlib


def test_default_root_is_v1(monkeypatch):
    monkeypatch.delenv("DRISHTI_DATA_VERSION", raising=False)
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.CACHE_DIR.name == "bloomberg"
    assert cfg.ARTIFACTS_DIR.name == "research_artifacts"


def test_v2_root_via_env(monkeypatch):
    monkeypatch.setenv("DRISHTI_DATA_VERSION", "v2")
    import src.config as cfg
    importlib.reload(cfg)
    assert cfg.CACHE_DIR.name == "bloomberg_v2"
    assert cfg.ARTIFACTS_DIR.name == "research_artifacts_v2"
    monkeypatch.delenv("DRISHTI_DATA_VERSION")
    importlib.reload(cfg)
