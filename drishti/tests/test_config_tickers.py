from src.config import SECTOR_TICKERS


def test_sector_tickers_use_valid_bloomberg_codes():
    # NSEOILGS / NSEMETAL do not exist on Bloomberg; correct = NSENRG / NSEMET
    assert SECTOR_TICKERS["energy"] == "NSENRG Index"
    assert SECTOR_TICKERS["metals"] == "NSEMET Index"
    for v in SECTOR_TICKERS.values():
        assert "NSEOILGS" not in v and "NSEMETAL" not in v
