import numpy as np
import pandas as pd
import pytest
from src.research.diagnostics import (
    adf_test, arch_lm_test, ljung_box,
    garch_order_scan, engle_sheppard_test, run_full_diagnostics
)


def _garch_series(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    r, s2 = [], 1e-4
    for _ in range(n):
        r.append(rng.normal(0, np.sqrt(s2)))
        s2 = 1e-6 + 0.08 * r[-1]**2 + 0.88 * s2
    return pd.Series(r, index=pd.date_range("2019-01-01", periods=n, freq="B"))


def test_adf_rejects_unit_root_for_returns():
    assert adf_test(_garch_series()).p_value < 0.01


def test_arch_lm_detects_clustering():
    assert arch_lm_test(_garch_series()).p_value < 0.05   # GARCH data → ARCH effects
    iid = pd.Series(np.random.default_rng(1).normal(0, 0.01, 1500))
    assert arch_lm_test(iid).p_value > 0.05               # iid → no ARCH


def test_ljung_box_on_std_residuals_after_garch():
    diag = run_full_diagnostics(_garch_series())
    # GARCH(1,1) fitted to its own DGP → std resid should have no autocorrelation
    assert diag["std_resid_lb_p"] > 0.05


def test_order_scan_returns_bic_table():
    tbl = garch_order_scan(_garch_series())
    assert {"garch_11", "garch_12", "garch_21", "gjr_11"} <= set(tbl)
    assert all(np.isfinite(v["bic"]) for v in tbl.values() if "error" not in v)


def test_engle_sheppard_constant_corr_not_rejected():
    rng = np.random.default_rng(2)
    z = rng.multivariate_normal([0, 0], [[1, .5], [.5, 1]], 1500) * 0.01
    df = pd.DataFrame(z, columns=["a", "b"],
                      index=pd.date_range("2019-01-01", periods=1500, freq="B"))
    result = engle_sheppard_test(df)
    assert result.p_value > 0.05
