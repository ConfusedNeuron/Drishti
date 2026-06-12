"""Market shock episode detection + per-episode cross-sectional statistics."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd


def detect_drawdown_episodes(px: pd.Series, threshold: float = 0.10) -> list[dict]:
    """Detect peak-to-trough drawdown episodes that breach *threshold* (e.g. 0.10 = 10%).

    Parameters
    ----------
    px : price series (must be positively valued)
    threshold : minimum drawdown depth to qualify as an episode (positive fraction)

    Returns
    -------
    List of dicts with keys:
        peak_date, trough_date, recovery_date (None if ongoing),
        depth (negative fraction), fall_days, recovery_days (None if ongoing)
    """
    px = px.dropna()
    if px.empty:
        return []

    peak_series = px.cummax()
    dd = px / peak_series - 1
    index_list = list(px.index)

    episodes: list[dict] = []
    in_ep = False
    ep_start_idx: int = 0

    for i, (dt, d) in enumerate(dd.items()):
        if not in_ep and d <= -threshold:
            in_ep = True
            ep_start_idx = i
        elif in_ep and d >= -1e-9:
            _append_episode(
                episodes, px, peak_series, dd,
                ep_start_idx, i, index_list, recovery_date=dt
            )
            in_ep = False

    # Handle episode still open at series end
    if in_ep:
        _append_episode(
            episodes, px, peak_series, dd,
            ep_start_idx, len(index_list) - 1, index_list, recovery_date=None
        )

    return episodes


def _append_episode(
    episodes: list[dict],
    px: pd.Series,
    peak_series: pd.Series,
    dd: pd.Series,
    ep_start_idx: int,
    ep_end_idx: int,
    index_list: list,
    recovery_date,
) -> None:
    seg = dd.iloc[ep_start_idx : ep_end_idx + 1]
    trough_date = seg.idxmin()
    trough_i = index_list.index(trough_date)

    # Peak date: last date at or before the trough where price equalled the running peak.
    # Using tolerance instead of exact equality handles float noise in constructed series.
    peak_val = float(peak_series.loc[trough_date])
    px_before_trough = px.iloc[: trough_i + 1]
    tolerance = peak_val * 1e-6 + 1e-9
    candidates = px_before_trough[np.abs(px_before_trough - peak_val) <= tolerance]
    if not candidates.empty:
        peak_date = candidates.index[-1]
    else:
        # Fallback: date of the cummax value closest to peak_val
        peak_date = (px_before_trough - peak_val).abs().idxmin()

    if recovery_date is not None:
        rec_days: int | None = int((recovery_date - trough_date).days)
    else:
        rec_days = None

    episodes.append({
        "peak_date": peak_date,
        "trough_date": trough_date,
        "recovery_date": recovery_date,
        "depth": float(seg.min()),
        "fall_days": int((trough_date - peak_date).days),
        "recovery_days": rec_days,
    })


def match_labels(episodes: list[dict], labels: list[dict]) -> list[dict]:
    """Attach a human-readable label and cause to each episode by window overlap.

    The first matching label (earliest in the list) wins.  Episodes that match
    no window are tagged "Unlabeled episode".
    """
    for e in episodes:
        e["label"] = "Unlabeled episode"
        e["cause"] = "unknown"
        end_date = e["recovery_date"] or e["trough_date"]
        for lab in labels:
            w0 = pd.Timestamp(lab["window"][0])
            w1 = pd.Timestamp(lab["window"][1])
            if e["peak_date"] <= w1 and end_date >= w0:
                e["label"] = lab["label"]
                e["cause"] = lab["cause"]
                break
    return episodes


def episode_stats(
    e: dict,
    sector_px: pd.DataFrame,
    valuations: pd.DataFrame | None = None,
) -> dict:
    """Compute cross-sectional crash statistics for one episode.

    Parameters
    ----------
    e : episode dict from detect_drawdown_episodes (modified in-place by match_labels)
    sector_px : price-level DataFrame, one column per sector/index
    valuations : optional valuation metric DataFrame (e.g. P/E) aligned to the same index

    Returns
    -------
    dict with:
        sector_falls        : {sector: return peak→trough}
        recovery_days       : {sector: calendar days trough→recovery, or None}
        first_to_recover    : sector name that recovered fastest (or None)
        positive_through    : list of sectors with positive return over the episode
        valuation_path      : (only if valuations supplied) peak / trough-date / end values
    """
    # Slice: peak→trough for fall magnitude (label-based slice, inclusive on both ends)
    fall_slice = sector_px.loc[e["peak_date"] : e["trough_date"]]

    if fall_slice.empty:
        return {
            "sector_falls": {},
            "recovery_days": {},
            "first_to_recover": None,
            "positive_through": [],
        }

    falls = (fall_slice.iloc[-1] / fall_slice.iloc[0] - 1).to_dict()

    end = e["recovery_date"] if e["recovery_date"] is not None else sector_px.index[-1]

    rec_days: dict[str, int | None] = {}
    for col in sector_px.columns:
        # Price at the peak date for this sector
        peak_prices = sector_px[col].loc[: e["peak_date"]]
        if peak_prices.empty or np.isnan(peak_prices.iloc[-1]):
            rec_days[col] = None
            continue
        target = float(peak_prices.iloc[-1])

        # Recovery window: trough → end
        rec_slice = sector_px[col].loc[e["trough_date"] : end]
        hit = rec_slice[rec_slice >= target]
        rec_days[col] = int((hit.index[0] - e["trough_date"]).days) if not hit.empty else None

    out: dict = {
        "sector_falls": {k: round(v, 4) for k, v in falls.items()},
        "recovery_days": rec_days,
        "first_to_recover": min(
            (k for k, v in rec_days.items() if v is not None),
            key=lambda k: rec_days[k],
            default=None,
        ),
        "positive_through": [k for k, v in falls.items() if v > 0],
    }

    if valuations is not None and not valuations.empty:
        window = valuations.loc[e["peak_date"] : end]
        if not window.empty:
            out["valuation_path"] = {
                col: {
                    "peak": float(window[col].iloc[0]),
                    "trough_date_value": float(
                        window[col].loc[: e["trough_date"]].iloc[-1]
                    ),
                    "end": float(window[col].iloc[-1]),
                }
                for col in window.columns
                if window[col].notna().any()
            }

    return out


def statistical_levels(episodes: list[dict]) -> dict:
    """Descriptive statistics of historical drawdown depths across all detected episodes.

    Returns median, 75th, 90th percentiles, and max fall — purely diagnostic,
    not a prediction or recommendation.
    """
    depths = [-e["depth"] for e in episodes if e["depth"] < 0]
    if not depths:
        return {"n_episodes": 0, "note": "No episodes found."}
    return {
        "n_episodes": len(depths),
        "median_fall": float(np.median(depths)),
        "p75_fall": float(np.percentile(depths, 75)),
        "p90_fall": float(np.percentile(depths, 90)),
        "max_fall": float(max(depths)),
        "note": (
            "Descriptive statistics of historical NIFTY drawdown depths; not predictions."
        ),
    }
