from src.copilot.safety import is_advice_request

BLOCK = [
    "should I buy RELIANCE?", "sell my INFY position", "is it a good time to invest",
    "recommend stocks", "go long on banks", "accumulate gold now", "exit my holdings?",
    "rebalance my portfolio for me", "which stock gives best returns",
]
PASS = [
    "what is my expected shortfall?", "explain my shareholding concentration",
    "why did VaR breach yesterday?", "what does the short-rate factor mean?",
    "how is the holding period defined?", "describe sector exposure",
]


def test_blocks_advice():
    for q in BLOCK:
        assert is_advice_request(q), f"should block: {q}"


def test_passes_diagnostics():
    for q in PASS:
        assert not is_advice_request(q), f"should pass: {q}"


def test_both_surfaces_use_shared_filter():
    import risk_mcp.tools as t, src.dashboard.routes.copilot as c, inspect
    assert "is_advice_request" in inspect.getsource(t)
    assert "is_advice_request" in inspect.getsource(c)
