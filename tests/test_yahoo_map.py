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


def test_hand_curated_divergences_recovered():
    """Regression test — d15a004 regenerated the map from the v2 universe and
    dropped these hand-curated divergences (see git show d15a004~1). Also
    covers the TTMT/A share-class-suffix key that bypasses the plain TTMT
    override and would otherwise yield the invalid candidate 'TTMT/A.NS'."""
    assert yahoo_candidate("AXSB IS Equity") == "AXISBANK.NS"
    assert yahoo_candidate("MM IS Equity") == "M&M.NS"
    assert yahoo_candidate("BJAUT IS Equity") == "BAJAJ-AUTO.NS"
    assert yahoo_candidate("TTMT/A IS Equity") == "TATAMOTORS.NS"
