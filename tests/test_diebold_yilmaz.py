import numpy as np
import pandas as pd

from src.research.diebold_yilmaz import compute_spillover


def test_net_spillovers_sum_to_zero():
    rng = np.random.default_rng(1)
    df = pd.DataFrame(
        rng.standard_normal((400, 4)),
        columns=list("abcd"),
        index=pd.date_range("2020-01-01", periods=400, freq="B"),
    )
    tbl = compute_spillover(df)
    assert abs(sum(tbl.net_spillover.values())) < 1e-6
