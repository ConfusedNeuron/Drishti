import numpy as np
import pandas as pd

from src.research.dcc_garch import fit_dcc_garch


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
