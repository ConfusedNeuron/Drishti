"""Yahoo candidate generation for the v2 universe."""
from scripts.build_yahoo_map_v2 import yahoo_candidate, build_equity_map


def test_direct_symbol():
    assert yahoo_candidate("RELIANCE IS Equity") == "RELIANCE.NS"


def test_known_divergent_codes():
    assert yahoo_candidate("HDFCB IS Equity") == "HDFCBANK.NS"
    assert yahoo_candidate("TTAN IS Equity") == "TITAN.NS"
    assert yahoo_candidate("INFO IS Equity") == "INFY.NS"


def test_build_equity_map_sorted_and_complete():
    m = build_equity_map(["TCS IS Equity", "HDFCB IS Equity"])
    assert m == {"HDFCB IS Equity": "HDFCBANK.NS", "TCS IS Equity": "TCS.NS"}
