"""
Portfolio importer — three paths:
  1. Sample JSON (always works, no network)
  2. CSV upload  (symbol, quantity, average_price; last_price optional)
  3. Zerodha Kite Connect API (requires valid access token)
"""
from __future__ import annotations
import csv
import io
import json
from datetime import datetime
from pathlib import Path

from src.bloomberg.tickers import registry
from src.config import SAMPLES_DIR
from src.models import Holding, PortfolioSnapshot


def _make_holding(symbol: str, exchange: str, quantity: float,
                  average_price: float, last_price: float) -> Holding:
    bbg = registry.resolve(symbol)
    sector = registry.sector(symbol)
    mv = quantity * last_price
    return Holding(
        symbol=symbol,
        exchange=exchange,
        bbg_ticker=bbg,
        quantity=quantity,
        average_price=average_price,
        last_price=last_price,
        market_value=mv,
        sector=sector,
        gics_sector=sector,
        asset_type="EQUITY",
        modeled=True,
        price_source="imported",
    )


def load_sample(sample_id: str = "nifty-demo-2026") -> PortfolioSnapshot:
    path = SAMPLES_DIR / f"{sample_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Sample '{sample_id}' not found at {path}")

    data = json.loads(path.read_text())
    holdings = []
    for h in data["holdings"]:
        last = h.get("last_price", h["average_price"])
        holding = _make_holding(
            symbol=h["symbol"],
            exchange=h.get("exchange", "NSE"),
            quantity=h["quantity"],
            average_price=h["average_price"],
            last_price=last,
        )
        holdings.append(holding)

    snap = _finalize(holdings, data.get("portfolio_id", sample_id), source="sample")
    return snap


def load_csv(content: str | bytes) -> PortfolioSnapshot:
    """
    CSV must have columns: symbol, quantity, average_price
    Optional: exchange, last_price
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    required = {"symbol", "quantity", "average_price"}
    rows = list(reader)
    if not rows:
        raise ValueError("CSV is empty")

    cols = {c.strip().lower() for c in rows[0].keys()}
    missing = required - cols
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")

    holdings = []
    unsupported = []
    for row in rows:
        sym = row.get("symbol", "").strip().upper()
        if not sym:
            continue
        try:
            qty = float(row["quantity"])
            avg = float(row["average_price"])
            last = float(row.get("last_price") or avg)
            exch = row.get("exchange", "NSE").strip().upper()
        except (ValueError, KeyError):
            unsupported.append(sym)
            continue

        # Skip F&O / MF rows by convention (symbol contains "FUT", "OPT", "CE", "PE")
        if any(x in sym for x in ("FUT", "OPT", "CE", "PE")):
            unsupported.append(sym)
            continue

        holdings.append(_make_holding(sym, exch, qty, avg, last))

    snap = _finalize(holdings, "csv-import", source="csv")
    if unsupported:
        snap.unsupported = unsupported  # type: ignore[attr-defined]
    return snap


def load_zerodha(access_token: str, api_key: str) -> PortfolioSnapshot:
    """Load holdings from Zerodha Kite Connect."""
    try:
        from kiteconnect import KiteConnect  # type: ignore
    except ImportError:
        raise RuntimeError("kiteconnect package not installed")

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    raw = kite.holdings()
    holdings = []
    for h in raw:
        sym = h["tradingsymbol"].upper()
        try:
            holding = _make_holding(
                symbol=sym,
                exchange=h.get("exchange", "NSE"),
                quantity=h["quantity"],
                average_price=h["average_price"],
                last_price=h.get("last_price", h["average_price"]),
            )
            holdings.append(holding)
        except Exception:
            continue

    return _finalize(holdings, "zerodha-live", source="zerodha")


def snapshot_from_rows(rows: list[dict], portfolio_id: str = "mcp-adhoc",
                       source: str = "mcp") -> PortfolioSnapshot:
    """Build a snapshot from plain dicts — the shape an MCP client passes
    after fetching holdings from a broker (e.g. Zerodha Kite MCP).
    Row: {"symbol", "quantity", "average_price", "last_price"?, "exchange"?}.
    Raises ValueError with a row-precise message on malformed input."""
    holdings = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"row {i} is not an object (got {type(row).__name__})")
        for key in ("symbol", "quantity", "average_price"):
            if key not in row:
                raise ValueError(f"row {i} missing key '{key}'")
        sym = str(row["symbol"]).strip().upper()
        if not sym:
            continue
        try:
            qty = float(row["quantity"])
            avg = float(row["average_price"])
            last = float(row.get("last_price") or avg)
        except (TypeError, ValueError):
            raise ValueError(
                f"row {i} ('{sym}'): quantity/average_price/last_price must be numeric"
            )
        exch = str(row.get("exchange", "NSE")).strip().upper()
        holdings.append(_make_holding(sym, exch, qty, avg, last))
    if not holdings:
        raise ValueError("No valid holdings rows supplied")
    return _finalize(holdings, portfolio_id, source)


def _finalize(holdings: list[Holding], portfolio_id: str, source: str) -> PortfolioSnapshot:
    total_mv = sum(h.market_value for h in holdings)
    for h in holdings:
        h.weight = h.market_value / total_mv if total_mv > 0 else 0.0

    return PortfolioSnapshot(
        portfolio_id=portfolio_id,
        holdings=holdings,
        total_value=total_mv,
        modeled_value=sum(h.market_value for h in holdings if h.modeled),
        source=source,
        as_of=datetime.now().isoformat(),
    )
