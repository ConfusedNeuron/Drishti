from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class Holding:
    symbol: str
    exchange: str
    bbg_ticker: str
    quantity: float
    average_price: float
    last_price: float
    market_value: float
    weight: float = 0.0
    sector: str = "Unknown"
    gics_sector: str = "Unknown"
    asset_type: str = "EQUITY"
    modeled: bool = True
    price_source: str = "cache"


@dataclass
class PortfolioSnapshot:
    portfolio_id: str
    holdings: list[Holding] = field(default_factory=list)
    total_value: float = 0.0
    modeled_value: float = 0.0
    source: str = "sample"
    as_of: str = ""

    @property
    def modeled_holdings(self) -> list[Holding]:
        return [h for h in self.holdings if h.modeled]

    @property
    def symbols(self) -> list[str]:
        return [h.symbol for h in self.modeled_holdings]

    @property
    def weights(self) -> dict[str, float]:
        return {h.symbol: h.weight for h in self.modeled_holdings}


@dataclass
class VaRResult:
    amount: float
    percent: float
    confidence: float
    horizon_days: int
    method: str
    obs: int = 0
    note: str = ""


@dataclass
class ESResult:
    amount: float
    percent: float
    confidence: float
    horizon_days: int
    tail_obs: int
    unstable: bool = False


@dataclass
class KupiecResult:
    lr_statistic: float
    p_value: float
    pass_: bool
    violations: int
    expected_violations: float
    violation_rate: float
    expected_rate: float


@dataclass
class ChristoffersenResult:
    lr_statistic: float
    p_value: float
    pass_: bool
    pi01: float
    pi11: float
    finding: str


@dataclass
class BacktestResult:
    confidence: float
    obs: int
    violations: int
    kupiec: KupiecResult
    christoffersen: ChristoffersenResult
    verdict: str


@dataclass
class RegimeLabel:
    regime: int          # 0 = low-vol, 1 = high-vol
    label: str
    posterior_prob: list[float]
    consecutive_days: int


@dataclass
class RegimeVaRResult:
    current_regime: int
    current_label: str
    low_vol_var: VaRResult
    high_vol_var: VaRResult


@dataclass
class ComponentContribution:
    symbol: str
    weight: float
    component_var: float
    var_share: float
    marginal_var: float


@dataclass
class StressResult:
    scenario: str
    description: str
    portfolio_loss: float
    loss_percent: float
    top_contributors: list[dict]
    affected_sectors: list[str]


@dataclass
class ICResult:
    factor: str
    target: str
    lag_days: int
    ic_mean: float
    ic_std: float
    icir: float
    t_stat: float
    p_value: float
    significant: bool
    bh_significant: bool = False   # after Benjamini-Hochberg correction


@dataclass
class GrangerResult:
    factor: str
    target: str
    lag: int
    f_stat: float
    p_value: float
    significant: bool


@dataclass
class DCCResult:
    """Time-varying conditional correlations from DCC-GARCH."""
    dates: list
    correlations: dict[str, pd.Series]  # e.g. {"brent_energy": Series}
    garch_params: dict


@dataclass
class SpilloverTable:
    """Diebold-Yilmaz connectedness table."""
    total_spillover: float
    to_spillover: dict[str, float]
    from_spillover: dict[str, float]
    net_spillover: dict[str, float]
    pairwise: pd.DataFrame
    var_lag: int
    fevd_horizon: int
