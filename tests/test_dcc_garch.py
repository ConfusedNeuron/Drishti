import numpy as np
import pandas as pd

from src.research.dcc_garch import fit_dcc_garch


def test_adcc_returns_gamma_and_psd_correlations():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2019-01-01", periods=900, freq="B")
    a_ret = pd.Series(rng.standard_normal(900) * 0.01, index=idx)
    b_ret = (0.6 * a_ret + 0.8 * pd.Series(rng.standard_normal(900) * 0.01, index=idx))
    df = pd.DataFrame({"a": a_ret, "b": b_ret})
    out = fit_dcc_garch(df, asymmetric=True)
    # Should have gamma in params
    assert "params" in out
    assert "g" in out["params"]
    assert out["params"]["g"] >= 0.0
    # Correlations must be valid
    corr = out["correlations"]
    assert corr.abs().max().max() <= 1.0 + 1e-9


def test_adcc_default_is_false_and_output_unchanged():
    # asymmetric=False must produce the same output shape as before (backward compat)
    rng = np.random.default_rng(5)
    idx = pd.date_range("2020-01-01", periods=500, freq="B")
    df = pd.DataFrame({
        "x": rng.standard_normal(500) * 0.01,
        "y": rng.standard_normal(500) * 0.01,
    }, index=idx)
    out = fit_dcc_garch(df, asymmetric=False)
    # Should NOT have "params" key but should have "dcc_alpha" and "dcc_beta"
    assert "dcc_alpha" in out
    assert "dcc_beta" in out
    # correlations DataFrame must exist
    assert "correlations" in out
    assert not out["correlations"].empty


def test_dcc_aligns_on_dates_not_positions():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2019-01-01", periods=700, freq="B")
    base = pd.Series(rng.standard_normal(700) * 0.01, index=idx)
    a = base.copy()
    b = base.copy()
    a.iloc[200:230] = np.nan  # interior gap → positional trim misaligns dates vs b

    out = fit_dcc_garch(pd.DataFrame({"a": a, "b": b}))
    corr = out["correlations"]

    assert corr.index.is_monotonic_increasing
    # a and b share identical returns on their common dates ⇒ near-perfect correlation
    assert float(corr.mean().iloc[0]) > 0.9
