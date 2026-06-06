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
