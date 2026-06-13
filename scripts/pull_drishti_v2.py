r"""
Drishti v2 Bloomberg pull — survivorship-free Nifty100 + Midcap150 universe since 2000.

Run at FRTL from the repo root (Windows):
  python scripts\pull_drishti_v2.py --validate          # field/ticker sanity, no big pulls
  python scripts\pull_drishti_v2.py --discover           # index membership -> universe manifest
  python scripts\pull_drishti_v2.py --indices --commodities --macro
  python scripts\pull_drishti_v2.py --equities           # the big one
  python scripts\pull_drishti_v2.py --sectors            # BDP GICS sector for whole universe
  python scripts\pull_drishti_v2.py --annual             # optional fundamentals
  python scripts\pull_drishti_v2.py --retry-failed       # re-attempt failure log

Writes ONLY to data/cache/bloomberg_v2/. Never touches data/cache/bloomberg/.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "data" / "cache" / "bloomberg_v2"
META_DIR = V2_DIR / "meta"
FAILED_LOG = META_DIR / "failed_v2.json"
UNIVERSE_MANIFEST = META_DIR / "universe_v2.json"

PULL_START = "20000101"
PULL_END = date.today().strftime("%Y%m%d")

MEMBERSHIP_INDICES = ["NSE100 Index", "NSEMD150 Index"]
MEMBERSHIP_FALLBACKS = ["NSEMCAP Index", "NSE500 Index"]   # if NSEMD150 has no pre-2016 history

EQUITY_DAILY_FIELDS = ["PX_LAST", "PX_VOLUME", "PE_RATIO", "PX_TO_BOOK_RATIO", "CUR_MKT_CAP"]
INDEX_FIELDS = ["PX_LAST", "PE_RATIO", "PX_TO_BOOK_RATIO"]   # valuation needed for events study
SIMPLE_FIELDS = ["PX_LAST"]                                   # commodities, macro

INDEX_TICKERS = [
    # v1 set
    "NSENRG Index", "NSEMET Index", "NSEFMCG Index", "NSEIT Index", "NSEBANK Index",
    "NSEAUTO Index", "NSEPHRM Index", "NSEREALTY Index", "NSEPSBK Index",
    "NSE200 Index", "NIFTY Index", "SENSEX Index", "NIFTYJR Index",
    # v2 additions (verified in data/csv/all nse index.csv)
    "NSE100 Index", "NSE500 Index", "NSEMD150 Index", "NSEMCAP Index", "NIFTYM50 Index",
    "NSESMCP Index", "NSES250 Index", "NSESM50 Index", "NSELM250 Index", "NSEMDSM Index",
    "NSEFIN Index", "NSEINFR Index", "NSECON Index", "NSECMD Index", "NSEMED Index", "NSEPSE Index",
]

COMMODITY_TICKERS = [
    # v1 set (extend history to 2000)
    "CO1 Comdty", "CL1 Comdty", "GC1 Comdty", "HG1 Comdty", "NG1 Comdty", "S 1 Comdty", "W 1 Comdty",
    # v2 additions — VERIFY AT TERMINAL via SECF before the big pull; alternates in comments
    "SI1 Comdty",       # COMEX silver front
    "LMAHDS03 Comdty",  # LME aluminium 3M; alt: LA1 Comdty
    "LMZSDS03 Comdty",  # LME zinc 3M;     alt: LX1 Comdty
    "SB1 Comdty",       # ICE sugar #11
    "CT1 Comdty",       # ICE cotton #2
    "KO1 Comdty",       # Bursa crude palm oil; alt: PAL... verify
    "XW1 Comdty",       # Newcastle coal; alts: API21MON Index, XA1 Comdty — verify
    "IOE1 Comdty",      # SGX iron ore 62%; alt: SCO1 Comdty — verify
]

MACRO_TICKERS = ["USDINR Curncy", "GIND10YR Index", "INVIXN Index", "DXY Curncy"]

# Reuse v1 plumbing — available on FRTL (tqdm installed); gracefully absent on Mac for dry import.
sys.path.insert(0, str(Path(__file__).parent))
try:
    from pull_drishti_data import (
        open_session, bdh, bdp, chunks, element_to_python,
        read_cached, write_to_cache, ticker_to_filename,
    )
except ImportError:
    open_session = bdh = bdp = chunks = element_to_python = read_cached = write_to_cache = ticker_to_filename = None  # type: ignore


def bds(session, ticker: str, field: str, overrides: dict[str, str] | None = None) -> list[dict]:
    """Bulk reference data request (BDS). Returns list of row-dicts."""
    import blpapi  # only available on FRTL
    svc = session.getService("//blp/refdata")
    req = svc.createRequest("ReferenceDataRequest")
    req.getElement("securities").appendValue(ticker)
    req.getElement("fields").appendValue(field)
    if overrides:
        ov_el = req.getElement("overrides")
        for k, v in overrides.items():
            ov = ov_el.appendElement()
            ov.setElement("fieldId", k)
            ov.setElement("value", v)
    session.sendRequest(req)

    rows: list[dict] = []
    while True:
        ev = session.nextEvent(30_000)
        for msg in ev:
            if not msg.hasElement("securityData"):
                continue
            sd_array = msg.getElement("securityData")
            for i in range(sd_array.numValues()):
                sd = sd_array.getValueAsElement(i)
                if sd.hasElement("securityError"):
                    raise RuntimeError(f"BDS error for {ticker}: {sd.getElement('securityError')}")
                fd = sd.getElement("fieldData")
                if not fd.hasElement(field):
                    continue
                bulk = fd.getElement(field)
                for j in range(bulk.numValues()):
                    row_el = bulk.getValueAsElement(j)
                    rows.append({
                        row_el.getElement(k).name().__str__(): element_to_python(row_el.getElement(k))
                        for k in range(row_el.numElements())
                    })
        if ev.eventType() == blpapi.Event.RESPONSE:
            break
    return rows


def _snapshot_dates(start_year: int = 2000) -> list[str]:
    """Jun-30 and Dec-31 of each year, YYYYMMDD."""
    out = []
    for y in range(start_year, date.today().year + 1):
        out += [f"{y}0630", f"{y}1231"]
    return [d for d in out if d <= PULL_END]


def discover_universe(session, with_fallbacks: bool = False) -> dict:
    """INDX_MWEIGHT_HIST snapshots -> {bbg_equity_ticker: metadata}. Writes manifest + raw snapshots."""
    META_DIR.mkdir(parents=True, exist_ok=True)
    (META_DIR / "membership").mkdir(exist_ok=True)

    indices = list(MEMBERSHIP_INDICES)
    if with_fallbacks:
        indices.extend(MEMBERSHIP_FALLBACKS)

    universe: dict[str, dict] = {}
    for idx in indices:
        for dt in _snapshot_dates():
            # INDX_MWEIGHT_HIST may return 0 rows on FRTL due to entitlement limits.
            # If all snapshots return empty, rerun --discover with INDX_MWEIGHT (no date override, current members only).
            try:
                rows = bds(session, idx, "INDX_MWEIGHT_HIST", {"END_DATE_OVERRIDE": dt})
            except Exception as e:
                print(f"  [WARN] {idx} @ {dt}: {e}")
                continue
            if not rows:
                continue
            snap_path = META_DIR / "membership" / f"{ticker_to_filename(idx)}_{dt}.json"
            snap_path.write_text(json.dumps(rows, indent=1, default=str))
            for r in rows:
                raw = (r.get("Index Member") or r.get("Member Ticker and Exchange Code") or "").strip()
                if not raw:
                    continue
                tkr = raw if raw.endswith("Equity") else f"{raw} Equity"
                rec = universe.setdefault(tkr, {"first_seen": dt, "last_seen": dt, "indices": []})
                rec["first_seen"] = min(rec["first_seen"], dt)
                rec["last_seen"] = max(rec["last_seen"], dt)
                if idx not in rec["indices"]:
                    rec["indices"].append(idx)
            print(f"  {idx} @ {dt}: {len(rows)} members (universe now {len(universe)})")

    UNIVERSE_MANIFEST.write_text(json.dumps(universe, indent=1, sort_keys=True))
    print(f"Universe manifest: {len(universe)} tickers -> {UNIVERSE_MANIFEST}")
    return universe


def _log_failure(ticker: str, group: str, err: str) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    log = json.loads(FAILED_LOG.read_text()) if FAILED_LOG.exists() else {}
    log[ticker] = {"group": group, "error": str(err)[:300], "at": date.today().isoformat()}
    FAILED_LOG.write_text(json.dumps(log, indent=1))


def pull_group_v2(session, tickers: list[str], fields: list[str], subdir: str,
                  batch: int = 25, equity_adjust: bool = False) -> None:
    out_dir = V2_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [t for t in tickers if not (out_dir / f"{ticker_to_filename(t)}.parquet").exists()]
    print(f"[{subdir}] {len(todo)}/{len(tickers)} to pull")
    for grp in chunks(todo, batch):
        try:
            if equity_adjust:
                df, errors_list = bdh(session, grp, fields, PULL_START, PULL_END,
                                      adj_split=True, adj_normal=True)
            else:
                df, errors_list = bdh(session, grp, fields, PULL_START, PULL_END)
        except Exception as e:
            for t in grp:
                _log_failure(t, subdir, str(e))
            continue
        error_set = set(errors_list)
        if not df.empty and "ticker" in df.columns:
            for t in grp:
                if t in error_set:
                    _log_failure(t, subdir, "Bloomberg security error")
                    continue
                t_df = df[df["ticker"] == t].drop(columns=["ticker"])
                if t_df.empty:
                    _log_failure(t, subdir, "empty response")
                else:
                    write_to_cache(out_dir / f"{ticker_to_filename(t)}.parquet", t_df)
        else:
            for t in errors_list:
                _log_failure(t, subdir, "Bloomberg security error")
            for t in grp:
                if t not in error_set:
                    _log_failure(t, subdir, "empty response")


def pull_sectors(session, tickers: list[str]) -> None:
    """GICS sector for every universe member -> meta/sectors_v2.json. BDP in batches of 20."""
    out: dict[str, dict] = {}
    for grp in chunks(tickers, 20):
        try:
            res = bdp(session, grp, ["GICS_SECTOR_NAME", "INDUSTRY_SECTOR", "NAME"])
            out.update(res)
        except Exception as e:
            for t in grp:
                _log_failure(t, "sectors", str(e))
    (META_DIR / "sectors_v2.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"sectors_v2.json: {len(out)} entries")


def validate(session) -> None:
    """5-day BDH on one known-good name per group + every NEW/UNVERIFIED ticker."""
    probes = {
        "equity fields":    (["RELIANCE IN Equity"], EQUITY_DAILY_FIELDS),
        "v1 failures":      (["LTIM IN Equity", "TTMT IN Equity"], ["PX_LAST"]),
        "new indices":      ([t for t in INDEX_TICKERS if any(x in t for x in
                               ("150", "SMCP", "S250", "NSELM", "NSEMDSM",
                                "NSE100", "NSEMCAP", "NSE500"))], INDEX_FIELDS),
        "new commodities":  (COMMODITY_TICKERS[7:], SIMPLE_FIELDS),
        "macro":            (MACRO_TICKERS, SIMPLE_FIELDS),
    }
    start = date.today().replace(day=1).strftime("%Y%m%d")
    for label, (tickers, fields) in probes.items():
        try:
            df, errors = bdh(session, tickers, fields, start, PULL_END)
            error_set = set(errors)
            for t in tickers:
                if t in error_set:
                    print(f"  [{label}] {t}: FAIL (security error)")
                elif df.empty or (not df.empty and "ticker" in df.columns and df[df["ticker"] == t].empty):
                    print(f"  [{label}] {t}: FAIL (no data)")
                else:
                    print(f"  [{label}] {t}: OK")
        except Exception as e:
            print(f"  [{label}] batch error: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Drishti v2 Bloomberg pull — survivorship-free Nifty100+Midcap150 since 2000.")
    for flag in ["validate", "discover", "with_fallbacks", "indices", "commodities",
                 "macro", "equities", "sectors", "annual", "retry_failed"]:
        ap.add_argument(f"--{flag.replace('_', '-')}", action="store_true")
    args = ap.parse_args()

    session = open_session()

    if args.validate:
        validate(session)
        return

    if args.discover:
        discover_universe(session, with_fallbacks=args.with_fallbacks)

    universe = json.loads(UNIVERSE_MANIFEST.read_text()) if UNIVERSE_MANIFEST.exists() else {}

    if args.indices:
        # De-duplicate INDEX_TICKERS (NSE100/NSEMD150 appear in both v1 and v2 additions)
        pull_group_v2(session, sorted(set(INDEX_TICKERS)), INDEX_FIELDS, "indices")
    if args.commodities:
        pull_group_v2(session, COMMODITY_TICKERS, SIMPLE_FIELDS, "commodities")
    if args.macro:
        pull_group_v2(session, MACRO_TICKERS, SIMPLE_FIELDS, "macro")
    if args.equities:
        pull_group_v2(session, sorted(universe), EQUITY_DAILY_FIELDS, "equities",
                      equity_adjust=True)
    if args.sectors:
        pull_sectors(session, sorted(universe))
    if args.annual:
        annual_fields = ["RETURN_COM_EQY", "BS_TOT_ASSET", "NET_INCOME",
                         "SHORT_AND_LONG_TERM_DEBT", "BOOK_VAL_PER_SH",
                         "EQY_DPS", "CF_CASH_FROM_OPER", "EQY_SH_OUT"]
        pull_group_v2(session, sorted(universe), annual_fields, "equities_annual",
                      batch=10)
    if args.retry_failed and FAILED_LOG.exists():
        log = json.loads(FAILED_LOG.read_text())
        by_group: dict[str, list[str]] = {}
        for t, rec in log.items():
            by_group.setdefault(rec["group"], []).append(t)
        FAILED_LOG.unlink()
        for grp_name, ts in by_group.items():
            if grp_name == "equities":
                pull_group_v2(session, ts, EQUITY_DAILY_FIELDS, grp_name, equity_adjust=True)
            elif grp_name == "indices":
                pull_group_v2(session, ts, INDEX_FIELDS, grp_name)
            else:
                pull_group_v2(session, ts, SIMPLE_FIELDS, grp_name)


if __name__ == "__main__":
    main()
