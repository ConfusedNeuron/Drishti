"""Component VaR and marginal VaR contributions."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

from src.models import ComponentContribution


def component_var(
    weights: np.ndarray,
    symbols: list[str],
    cov_matrix: np.ndarray,
    portfolio_value: float,
    confidence: float = 0.99,
) -> list[ComponentContribution]:
    """
    Component VaR = w_i * (Σ w)_i / σ_p * z * portfolio_value

    where (Σ w)_i is the i-th element of the portfolio covariance vector,
    σ_p = sqrt(w' Σ w), and z = Φ^{-1}(confidence).

    Component VaRs sum to total parametric VaR by construction.
    """
    w = np.array(weights)
    cov = np.array(cov_matrix)

    port_variance = float(w @ cov @ w)
    port_std = np.sqrt(port_variance)
    z = stats.norm.ppf(confidence)

    cov_vec = cov @ w          # vector of covariances between each asset and portfolio
    marginal_var = cov_vec / port_std * z   # per-unit marginal VaR
    comp_var = w * marginal_var             # component VaR (return scale)

    total_var = float(port_std * z * portfolio_value)

    results = []
    for i, sym in enumerate(symbols):
        cv_amount = float(comp_var[i] * portfolio_value)
        results.append(ComponentContribution(
            symbol=sym,
            weight=float(w[i]),
            component_var=cv_amount,
            var_share=cv_amount / total_var if total_var != 0 else 0.0,
            marginal_var=float(marginal_var[i]),
        ))

    results.sort(key=lambda x: abs(x.component_var), reverse=True)
    return results
