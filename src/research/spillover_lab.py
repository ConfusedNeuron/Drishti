"""Spillover Lab: pick any 3-12 cached series and compute Diebold-Yilmaz
connectedness live. Pure compute core — catalog listing, id resolution to an
aligned daily-return panel, and a capped runner. Educational/diagnostic only,
no investment-advice language.
"""
from __future__ import annotations

import pandas as pd

from src.config import DATA_DIR
from src.research.series_io import load_index_prices, load_commodity_prices, load_macro_prices
from src.research.universe import (load_universe, load_sectors, build_size_buckets,
                                    sector_composites, load_v2_returns)
from src.research.diebold_yilmaz import compute_spillover, rolling_spillover

CACHE_DIR = DATA_DIR / "cache" / "bloomberg_v2"

CAPS = {"min_series": 3, "max_series": 12, "min_obs": 250,
        "window": (100, 500), "step": (5, 63), "horizon": (5, 20)}

# Macro tickers that are yields/rates rather than prices — differenced, not
# pct_change'd (mirrors the gsec10y convention in src/risk/returns.py).
_YIELD_MACRO = {"GIND10YR Index"}


def _list_parquet_tickers(subdir: str) -> list[str]:
    d = CACHE_DIR / subdir
    if not d.exists():
        return []
    return sorted(p.stem.replace("_", " ") for p in d.glob("*.parquet"))


def build_catalog() -> dict:
    """List every series pickable for the lab, grouped by category.
    Only lists what actually exists on disk / in the universe manifest, so
    the catalog degrades gracefully on a synthetic or partial cache."""
    manifest = load_universe()
    sectors = load_sectors()

    equities = []
    for full in sorted(manifest, key=lambda t: t.replace(" IS Equity", "")):
        symbol = full.replace(" IS Equity", "")
        sector = sectors.get(full, "Unknown")
        equities.append({"id": f"eq:{symbol}", "label": f"{symbol} — {sector}"})

    indices = [{"id": f"idx:{t}", "label": t} for t in _list_parquet_tickers("indices")]
    commodities = [{"id": f"cmd:{t}", "label": t} for t in _list_parquet_tickers("commodities")]
    macro = [{"id": f"mac:{t}", "label": t} for t in _list_parquet_tickers("macro")]

    buckets = build_size_buckets(manifest)
    composites = []
    for bucket in ["large", "mid"]:
        counts: dict[str, int] = {}
        for ticker in buckets.get(bucket, []):
            sector = sectors.get(ticker, "Unknown")
            if sector == "Unknown":
                continue
            counts[sector] = counts.get(sector, 0) + 1
        for sector, n in counts.items():
            if n >= 2:
                composites.append({
                    "id": f"sec:{sector}|{bucket}",
                    "label": f"{sector} ({bucket}-cap composite)",
                })
    composites.sort(key=lambda c: c["label"])

    return {
        "equities": equities,
        "indices": indices,
        "commodities": commodities,
        "macro": macro,
        "sector_composites": composites,
    }


def _resolve_sec_ids(sec_ids: list[str]) -> dict[str, pd.Series]:
    """Resolve every sec:Sector|bucket id, batching one load_v2_returns +
    sector_composites call per bucket (each call reads 200+ parquets)."""
    by_bucket: dict[str, list[tuple[str, str]]] = {}
    for sid in sec_ids:
        rest = sid[len("sec:"):]
        sector, _, bucket = rest.partition("|")
        by_bucket.setdefault(bucket, []).append((sid, sector))

    manifest = load_universe()
    buckets = build_size_buckets(manifest)
    sectors = load_sectors()

    out: dict[str, pd.Series] = {}
    for bucket, items in by_bucket.items():
        tickers = buckets.get(bucket, [])
        rets = load_v2_returns(tickers) if tickers else pd.DataFrame()
        comps = sector_composites(rets, sectors, bucket=tickers) if not rets.empty else pd.DataFrame()
        for sid, sector in items:
            if sector in comps.columns:
                out[sid] = comps[sector]
    return out


def resolve_series(series_ids: list[str], start, end) -> pd.DataFrame:
    """Resolve catalog ids into an aligned daily-return panel.

    Each series is sliced to [start, end] before alignment; the panel is
    then inner-joined across all series and NaN rows dropped.
    """
    columns: dict[str, pd.Series] = {}
    unknown: list[str] = []

    eq_ids = [s for s in series_ids if s.startswith("eq:")]
    idx_ids = [s for s in series_ids if s.startswith("idx:")]
    cmd_ids = [s for s in series_ids if s.startswith("cmd:")]
    mac_ids = [s for s in series_ids if s.startswith("mac:")]
    sec_ids = [s for s in series_ids if s.startswith("sec:")]
    known_prefixed = set(eq_ids) | set(idx_ids) | set(cmd_ids) | set(mac_ids) | set(sec_ids)
    unknown.extend(s for s in series_ids if s not in known_prefixed)

    for sid in eq_ids:
        symbol = sid[len("eq:"):]
        ticker = f"{symbol} IS Equity"
        rets = load_v2_returns([ticker])
        if rets is None or rets.empty or ticker not in rets.columns:
            unknown.append(sid)
            continue
        columns[symbol] = rets[ticker].loc[start:end]

    for sid in idx_ids:
        ticker = sid[len("idx:"):]
        px = load_index_prices([ticker])
        if px is None or px.empty or ticker not in px.columns:
            unknown.append(sid)
            continue
        columns[ticker] = px[ticker].pct_change().loc[start:end]

    for sid in cmd_ids:
        ticker = sid[len("cmd:"):]
        px = load_commodity_prices([ticker])
        if px is None or px.empty or ticker not in px.columns:
            unknown.append(sid)
            continue
        columns[ticker] = px[ticker].pct_change().loc[start:end]

    for sid in mac_ids:
        ticker = sid[len("mac:"):]
        px = load_macro_prices([ticker])
        if px is None or px.empty or ticker not in px.columns:
            unknown.append(sid)
            continue
        level = px[ticker]
        ret = level.diff() if ticker in _YIELD_MACRO else level.pct_change()
        columns[ticker] = ret.loc[start:end]

    if sec_ids:
        resolved_sec = _resolve_sec_ids(sec_ids)
        for sid in sec_ids:
            if sid not in resolved_sec:
                unknown.append(sid)
                continue
            rest = sid[len("sec:"):]
            sector, _, bucket = rest.partition("|")
            label = f"{sector} ({bucket})"
            columns[label] = resolved_sec[sid].loc[start:end]

    if unknown:
        raise ValueError("Unknown series ids: " + ", ".join(unknown))

    # Slice happened per-series above; now align across all series.
    panel = pd.DataFrame(columns)
    panel = panel.loc[:, ~panel.columns.duplicated()]
    return panel.dropna(how="any")


def run_custom_spillover(series_ids, start=None, end=None, fevd_horizon=10,
                          rolling=False, window=200, step=21) -> dict:
    """Capped, user-driven Diebold-Yilmaz connectedness run. Educational
    diagnostic only — not a trading signal."""
    n = len(series_ids)
    if n < CAPS["min_series"]:
        raise ValueError(f"Need at least {CAPS['min_series']} series, got {n}")
    if n > CAPS["max_series"]:
        raise ValueError(f"Too many series: {n} (max {CAPS['max_series']})")

    lo, hi = CAPS["horizon"]
    if not (lo <= fevd_horizon <= hi):
        raise ValueError(f"fevd_horizon {fevd_horizon} out of range [{lo}, {hi}]")

    if rolling:
        lo, hi = CAPS["window"]
        if not (lo <= window <= hi):
            raise ValueError(f"window {window} out of range [{lo}, {hi}]")
        lo, hi = CAPS["step"]
        if not (lo <= step <= hi):
            raise ValueError(f"step {step} out of range [{lo}, {hi}]")

    panel = resolve_series(series_ids, start, end)

    n_obs = len(panel)
    if n_obs < CAPS["min_obs"]:
        raise ValueError(
            f"Only {n_obs} aligned observations after date/NaN alignment; need ≥{CAPS['min_obs']}"
        )

    tbl = compute_spillover(panel, fevd_horizon=fevd_horizon)

    rolling_out = None
    dropped_note = None
    if rolling:
        if n_obs >= window + step:
            roll = rolling_spillover(panel, window=window, step=step, fevd_horizon=fevd_horizon)
            rolling_out = {
                "dates": [d.date().isoformat() for d in roll.index],
                "values": [round(float(v), 2) for v in roll.values],
            }
        else:
            dropped_note = (
                f"Rolling connectedness skipped: only {n_obs} observations, "
                f"need at least window+step={window + step}"
            )

    return {
        "total_connectedness": tbl.total_spillover,
        "to_spillover": tbl.to_spillover,
        "from_spillover": tbl.from_spillover,
        "net_spillover": tbl.net_spillover,
        "pairwise": tbl.pairwise.to_dict(),
        "var_lag": tbl.var_lag,
        "fevd_horizon": tbl.fevd_horizon,
        "rolling": rolling_out,
        "meta": {
            "n_series": len(panel.columns),
            "n_obs": n_obs,
            "start": str(panel.index.min().date()),
            "end": str(panel.index.max().date()),
            "labels": list(panel.columns),
            "dropped_note": dropped_note,
        },
    }
