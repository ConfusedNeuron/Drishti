import numpy as np
from types import SimpleNamespace

from src.research.hmm import _high_vol_prob_column


def test_high_vol_prob_column_picks_canonical_high_vol_state():
    # raw state 0 is HIGH vol (emission mean 0.30), raw state 1 is LOW vol (0.10)
    fake = SimpleNamespace(means_=np.array([[0.30], [0.10]]))
    assert _high_vol_prob_column(fake) == 0  # must pick raw column 0, not hardcoded 1

    fake2 = SimpleNamespace(means_=np.array([[0.10], [0.40]]))
    assert _high_vol_prob_column(fake2) == 1
