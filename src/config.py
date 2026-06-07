from datetime import date, timedelta
from pathlib import Path
from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache" / "bloomberg"
SAMPLES_DIR = DATA_DIR / "samples"
MAPPINGS_DIR = DATA_DIR / "mappings"
ARTIFACTS_DIR = DATA_DIR / "cache" / "research_artifacts"

for _d in [CACHE_DIR, SAMPLES_DIR, MAPPINGS_DIR, ARTIFACTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


def default_dates() -> tuple[date, date]:
    """Return (start, end) spanning the last 5 years ending yesterday."""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=365 * 5)
    return start, end


class Settings(BaseSettings):
    bloomberg_host: str = "localhost"
    bloomberg_port: int = 8194
    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""
    zerodha_access_token: str = ""
    llm_api_key: str = ""

    class Config:
        env_file = ROOT / ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# ── Bloomberg ticker registry ──────────────────────────────────────────────
COMMODITY_TICKERS = {
    "brent":   "CO1 Comdty",
    "wti":     "CL1 Comdty",
    "gold":    "GC1 Comdty",
    "copper":  "HG1 Comdty",
    "natgas":  "NG1 Comdty",
}

MACRO_TICKERS = {
    "usdinr":  "USDINR Curncy",
    "gsec10y": "GIND10YR Index",
    "indiavix":"INVIXN Index",
}

SECTOR_TICKERS = {
    "energy":   "NSENRG Index",
    "metals":   "NSEMET Index",
    "fmcg":     "NSEFMCG Index",
    "it":       "NSEIT Index",
    "banks":    "NSEBANK Index",
    "auto":     "NSEAUTO Index",
    "pharma":   "NSEPHRM Index",
}

BENCHMARK_TICKERS = {
    "nifty50":  "NIFTY Index",
    "sensex":   "SENSEX Index",
}

ALL_FACTOR_TICKERS = {**COMMODITY_TICKERS, **MACRO_TICKERS}

# Stress scenario shocks (factor → sector return impact)
STRESS_SCENARIOS = {
    "covid_march2020": {
        "description": "COVID crash — March 2020 peak-to-trough",
        "equity_shock": -0.35,
        "sector_overrides": {"energy": -0.45, "metals": -0.40, "banks": -0.42},
        "vol_multiplier": 3.0,
    },
    "crude_shock_2022": {
        "description": "Oil price shock — 2022 commodity spike",
        "sector_overrides": {"energy": +0.12, "metals": +0.08, "fmcg": -0.06, "it": -0.04},
        "equity_shock": -0.10,
        "vol_multiplier": 1.5,
    },
    "rate_hike_100bps": {
        "description": "RBI rate hike +100 bps",
        "sector_overrides": {"banks": -0.08, "fmcg": -0.04, "it": -0.03},
        "equity_shock": -0.05,
        "vol_multiplier": 1.2,
    },
    "inr_depreciation_10pct": {
        "description": "INR depreciates 10% vs USD",
        "sector_overrides": {"it": +0.06, "pharma": +0.04, "energy": -0.08, "fmcg": -0.05},
        "equity_shock": -0.03,
        "vol_multiplier": 1.3,
    },
    "election_volatility": {
        "description": "Election uncertainty — broad vol spike",
        "equity_shock": -0.05,
        "sector_overrides": {},
        "vol_multiplier": 2.0,
    },
}
