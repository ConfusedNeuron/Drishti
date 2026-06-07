from src.bloomberg.tickers import registry

CORRECT = {
    "HDFCBANK": "HDFCB IN Equity", "INFY": "INFO IN Equity",
    "ICICIBANK": "ICICIBC IN Equity", "KOTAKBANK": "KMB IN Equity",
    "BAJFINANCE": "BAF IN Equity", "HINDUNILVR": "HUVR IN Equity",
    "HCLTECH": "HCLT IN Equity", "WIPRO": "WPRO IN Equity",
    "NESTLEIND": "NEST IN Equity", "ASIANPAINT": "APNT IN Equity",
    "TATAMOTORS": "TTMT IN Equity", "HINDALCO": "HNDL IN Equity",
    "POWERGRID": "PWGR IN Equity", "TATASTEEL": "TATA IN Equity",
    "TITAN": "TTAN IN Equity", "MARUTI": "MSIL IN Equity",
}


def test_builtin_tickers_match_bloomberg_codes():
    for nse, bbg in CORRECT.items():
        assert registry.resolve(nse) == bbg


def test_tataconsum_not_priced_as_tata_motors():
    assert registry.resolve("TATACONSUM") != "TTMT IN Equity"


def test_sample_holdings_resolve_to_cached_data():
    """Every sample-portfolio holding must resolve to a ticker present in the
    cache. Guards the silent-drop bug where a registry mis-resolution (e.g.
    HDFCBANK -> 'HDFCBANK IN Equity' instead of the real 'HDFCB IN Equity')
    makes get_prices return None and the holding vanish. Skips when no cache
    is present (e.g. CI / fresh clone)."""
    import pytest

    from src.bloomberg.cache import get_prices, list_cached_tickers
    from src.config import default_dates
    from src.portfolio.importer import load_sample

    if not list_cached_tickers():
        pytest.skip("no Bloomberg/synthetic cache present")

    snap = load_sample()
    start, end = default_dates()
    missing = [
        h.symbol
        for h in snap.modeled_holdings
        if get_prices(h.bbg_ticker, start, end, "PX_LAST") is None
    ]
    assert missing == [], f"silent cache miss for {missing} — registry/cache name mismatch"
