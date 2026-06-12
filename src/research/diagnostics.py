"""Model-identification diagnostics: the ladder the GARCH/DCC choices stand on."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class TestResult:
    name: str
    statistic: float
    p_value: float
    conclusion: str


def adf_test(returns: pd.Series) -> TestResult:
    from statsmodels.tsa.stattools import adfuller
    stat, p, *_ = adfuller(returns.dropna().values, autolag="AIC")
    return TestResult("ADF", float(stat), float(p),
                      "stationary" if p < 0.05 else "unit root not rejected")


def ljung_box(series: pd.Series, lags: int = 10) -> TestResult:
    from statsmodels.stats.diagnostic import acorr_ljungbox
    out = acorr_ljungbox(series.dropna().values, lags=[lags], return_df=True)
    p = float(out["lb_pvalue"].iloc[0])
    return TestResult(f"Ljung-Box({lags})", float(out["lb_stat"].iloc[0]), p,
                      "autocorrelated" if p < 0.05 else "no autocorrelation")


def arch_lm_test(returns: pd.Series, lags: int = 10) -> TestResult:
    from statsmodels.stats.diagnostic import het_arch
    stat, p, *_ = het_arch(returns.dropna().values, nlags=lags)
    return TestResult(f"ARCH-LM({lags})", float(stat), float(p),
                      "ARCH effects present" if p < 0.05 else "no ARCH effects")


def garch_order_scan(returns: pd.Series) -> dict[str, dict]:
    """BIC comparison: GARCH(1,1)/(1,2)/(2,1) + GJR(1,1). Returns {model: {bic, aic, ...}}."""
    from arch import arch_model
    r = returns.dropna() * 100
    specs = {
        "garch_11": dict(vol="GARCH", p=1, q=1),
        "garch_12": dict(vol="GARCH", p=1, q=2),
        "garch_21": dict(vol="GARCH", p=2, q=1),
        "gjr_11":   dict(vol="GARCH", p=1, o=1, q=1),
    }
    out = {}
    for name, spec in specs.items():
        try:
            res = arch_model(r, dist="normal", rescale=False, **spec).fit(
                disp="off", show_warning=False)
            row = {"bic": float(res.bic), "aic": float(res.aic)}
            if name == "gjr_11":
                row["gamma"] = float(res.params.get("gamma[1]", np.nan))
                row["gamma_p"] = float(res.pvalues.get("gamma[1]", np.nan))
            out[name] = row
        except Exception as e:
            out[name] = {"bic": float("nan"), "aic": float("nan"), "error": str(e)[:120]}
    return out


def engle_sheppard_test(returns_df: pd.DataFrame, lags: int = 5) -> TestResult:
    """H0: constant conditional correlation. Regression form of Engle-Sheppard (2001).
    GARCH-standardize each series, CCC-whiten jointly, regress mean off-diagonal
    deviation on its lags; joint Wald that all lag coefs = 0."""
    from arch import arch_model
    import statsmodels.api as sm

    Z = {}
    for c in returns_df.columns:
        res = arch_model(returns_df[c].dropna() * 100, vol="GARCH", p=1, q=1,
                         dist="normal", rescale=False).fit(disp="off", show_warning=False)
        Z[c] = res.std_resid.dropna()
    Zdf = pd.concat(Z, axis=1).dropna()

    R = np.corrcoef(Zdf.values.T)
    try:
        Rinv_sqrt = np.linalg.inv(np.linalg.cholesky(R))
    except np.linalg.LinAlgError:
        R += np.eye(len(R)) * 1e-8
        Rinv_sqrt = np.linalg.inv(np.linalg.cholesky(R))

    U = Zdf.values @ Rinv_sqrt.T          # CCC-whitened residuals
    k = U.shape[1]
    iu = np.triu_indices(k, 1)
    # Mean off-diagonal deviation per time step
    y_t = np.array([np.outer(u, u)[iu].mean() for u in U])

    X = np.column_stack(
        [np.ones(len(y_t) - lags)] +
        [y_t[lags - j - 1: len(y_t) - j - 1] for j in range(lags)]
    )
    y = y_t[lags:]
    ols = sm.OLS(y, X).fit()

    # Wald test: all lag coefficients = 0 (indices 1..lags, skipping the intercept)
    r_matrix = np.zeros((lags, lags + 1))
    for i in range(lags):
        r_matrix[i, i + 1] = 1.0
    wald = ols.wald_test(r_matrix, scalar=True)
    p = float(wald.pvalue)
    return TestResult("Engle-Sheppard CCC", float(wald.statistic), p,
                      "dynamic correlation (reject CCC)" if p < 0.05 else "CCC not rejected")


def run_full_diagnostics(returns: pd.Series) -> dict:
    """The univariate ladder for one series."""
    from arch import arch_model
    res = arch_model(returns.dropna() * 100, vol="GARCH", p=1, q=1,
                     dist="normal", rescale=False).fit(disp="off", show_warning=False)
    z = pd.Series(res.std_resid).dropna()
    return {
        "adf": adf_test(returns).__dict__,
        "returns_lb": ljung_box(returns).__dict__,
        "arch_lm": arch_lm_test(returns).__dict__,
        "order_scan": garch_order_scan(returns),
        "std_resid_lb_p": ljung_box(z).p_value,
        "std_resid_sq_lb_p": ljung_box(z**2).p_value,
    }
