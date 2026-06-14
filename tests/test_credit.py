import math
from src.research import credit

def test_altman_z_safe_zone():
    z = credit.altman_z(working_capital=40, retained_earnings=60, ebit=30,
                        mkt_value_equity=200, total_liabilities=80, sales=150,
                        total_assets=100)
    assert z["z"] > 2.99 and z["zone"] == "safe"
    assert abs(z["z"] - 5.31) < 1e-6        # validator-computed value

def test_altman_z_distress_zone():
    z = credit.altman_z(working_capital=-10, retained_earnings=-20, ebit=-5,
                        mkt_value_equity=10, total_liabilities=90, sales=20,
                        total_assets=100)
    assert z["z"] < 1.81 and z["zone"] == "distress"

def test_altman_z_guards_zero_denominator():
    z = credit.altman_z(1, 1, 1, 1, 0, 1, 100)
    assert math.isnan(z["z"]) and z["zone"] == "n/a"
