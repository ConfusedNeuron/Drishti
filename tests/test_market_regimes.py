import numpy as np
import pandas as pd
from src.research.market_regimes import classify_bull_bear, regime_signs, current_state


def test_twenty_percent_rule_labels_constructed_cycle():
    idx = pd.date_range("2020-01-01", periods=750, freq="B")
    px = pd.Series(np.concatenate([
        np.linspace(100, 150, 250),    # +50% bull
        np.linspace(150, 100, 250),    # -33% bear (exceeds 20%)
        np.linspace(100, 140, 250),    # +40% bull
    ]), index=idx)
    reg = classify_bull_bear(px)
    assert reg.iloc[100] == "bull"
    assert reg.iloc[400] == "bear"
    assert reg.iloc[700] == "bull"


def test_regime_signs_has_expected_keys():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    returns = pd.Series(np.random.default_rng(0).normal(0, 0.01, 300), index=idx)
    px = (1 + returns).cumprod() * 100
    regimes = classify_bull_bear(px)
    signs = regime_signs(returns, regimes)
    # At least bull regime should be present (monotone up by construction is unlikely, but any regime)
    for reg_name in signs:
        assert {"ann_vol", "mean_daily_ret", "worst_day", "skew"} <= set(signs[reg_name])


def test_current_state_has_expected_keys():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    px = pd.Series(np.linspace(100, 130, 300), index=idx)
    regimes = classify_bull_bear(px)
    cs = current_state(px, regimes)
    assert {"regime", "drawdown_from_peak", "pct_to_bear_threshold", "hmm_prob_high_vol", "note"} <= set(cs)
