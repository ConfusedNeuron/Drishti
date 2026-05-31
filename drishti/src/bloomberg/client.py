"""
Bloomberg BLPAPI client with parquet cache fallback.

Usage at FRTL (Bloomberg terminal must be running):
    client = BloombergClient().connect()
    df = client.bdh(["RELIANCE IN Equity"], ["PX_ADJ_CLOSE"], "20210101", "20260514")

Offline (cache-only) mode:
    from src.bloomberg.cache import get_prices
    series = get_prices("RELIANCE IN Equity", start, end)
"""
from __future__ import annotations
import logging
import time
from datetime import date, datetime
from typing import Optional

import pandas as pd

from src.bloomberg import cache as bbg_cache

logger = logging.getLogger(__name__)

_BLPAPI_AVAILABLE = False
try:
    import blpapi  # type: ignore
    _BLPAPI_AVAILABLE = True
except ImportError:
    logger.warning("blpapi not installed — Bloomberg API unavailable. Cache-only mode.")


class BloombergClient:
    """
    Thin wrapper around BLPAPI.
    Falls back to parquet cache if Bloomberg session cannot be established.
    """

    def __init__(self, host: str = "localhost", port: int = 8194):
        self.host = host
        self.port = port
        self.session: Optional[object] = None
        self._connected = False

    def connect(self) -> "BloombergClient":
        if not _BLPAPI_AVAILABLE:
            logger.warning("blpapi unavailable — running in cache-only mode.")
            return self
        try:
            opts = blpapi.SessionOptions()
            opts.setServerHost(self.host)
            opts.setServerPort(self.port)
            self.session = blpapi.Session(opts)
            if not self.session.start():
                raise ConnectionError("Bloomberg session failed to start")
            if not self.session.openService("//blp/refdata"):
                raise ConnectionError("Could not open //blp/refdata service")
            self._connected = True
            logger.info("Bloomberg session connected at %s:%d", self.host, self.port)
        except Exception as e:
            logger.warning("Bloomberg connection failed (%s) — cache-only mode.", e)
        return self

    @property
    def connected(self) -> bool:
        return self._connected

    def bdh(self,
            securities: list[str],
            fields: list[str],
            start_date: str,
            end_date: str,
            periodicity: str = "DAILY",
            adj_split: bool = True,
            adj_normal: bool = True,
            chunk_size: int = 100,
            sleep_secs: float = 0.25) -> pd.DataFrame:
        """
        Historical data request.

        start_date / end_date: "YYYYMMDD"
        Returns DataFrame with MultiIndex (date, ticker) or date index if single ticker.
        Writes results to parquet cache.
        """
        if not self._connected:
            return self._bdh_from_cache(securities, fields, start_date, end_date)

        all_dfs = []
        for i in range(0, len(securities), chunk_size):
            chunk = securities[i: i + chunk_size]
            df = self._bdh_request(chunk, fields, start_date, end_date,
                                   periodicity, adj_split, adj_normal)
            all_dfs.append(df)
            if i + chunk_size < len(securities):
                time.sleep(sleep_secs)

        result = pd.concat(all_dfs) if all_dfs else pd.DataFrame()

        # Cache each ticker
        for ticker in securities:
            if ticker in result.index.get_level_values("ticker"):
                ticker_df = result.xs(ticker, level="ticker")[fields]
                bbg_cache.write_cache(ticker, ticker_df)

        return result

    def bdp(self, securities: list[str], fields: list[str]) -> dict[str, dict]:
        """Reference data request. Returns {ticker: {field: value}}."""
        if not self._connected:
            return {}
        return self._bdp_request(securities, fields)

    # ── Internal BLPAPI request methods ──────────────────────────────────

    def _bdh_request(self, securities, fields, start_date, end_date,
                     periodicity, adj_split, adj_normal) -> pd.DataFrame:
        svc = self.session.getService("//blp/refdata")
        req = svc.createRequest("HistoricalDataRequest")
        for sec in securities:
            req.getElement("securities").appendValue(sec)
        for fld in fields:
            req.getElement("fields").appendValue(fld)
        req.set("startDate", start_date)
        req.set("endDate", end_date)
        req.set("periodicitySelection", periodicity)
        req.set("adjustmentSplit", adj_split)
        req.set("adjustmentNormal", adj_normal)
        self.session.sendRequest(req)

        rows = []
        done = False
        while not done:
            ev = self.session.nextEvent(500)
            for msg in ev:
                if msg.hasElement("securityData"):
                    sec_data = msg.getElement("securityData")
                    ticker = sec_data.getElementAsString("security")
                    field_data_arr = sec_data.getElement("fieldData")
                    for j in range(field_data_arr.numValues()):
                        fd = field_data_arr.getValue(j)
                        row = {"ticker": ticker, "date": fd.getElementAsDatetime("date")}
                        for fld in fields:
                            try:
                                row[fld] = fd.getElementAsFloat(fld)
                            except Exception:
                                row[fld] = None
                        rows.append(row)
            if ev.eventType() == blpapi.Event.RESPONSE:
                done = True

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index(["date", "ticker"])
        return df

    def _bdp_request(self, securities, fields) -> dict:
        svc = self.session.getService("//blp/refdata")
        req = svc.createRequest("ReferenceDataRequest")
        for sec in securities:
            req.getElement("securities").appendValue(sec)
        for fld in fields:
            req.getElement("fields").appendValue(fld)
        self.session.sendRequest(req)

        result = {}
        done = False
        while not done:
            ev = self.session.nextEvent(500)
            for msg in ev:
                if msg.hasElement("securityData"):
                    arr = msg.getElement("securityData")
                    for i in range(arr.numValues()):
                        sec_el = arr.getValue(i)
                        ticker = sec_el.getElementAsString("security")
                        fd = sec_el.getElement("fieldData")
                        result[ticker] = {}
                        for fld in fields:
                            try:
                                result[ticker][fld] = fd.getElementAsString(fld)
                            except Exception:
                                result[ticker][fld] = None
            if ev.eventType() == blpapi.Event.RESPONSE:
                done = True
        return result

    def _bdh_from_cache(self, securities, fields, start_date, end_date) -> pd.DataFrame:
        """Return whatever is in cache for the given securities."""
        start = datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.strptime(end_date, "%Y%m%d").date()
        rows = []
        for ticker in securities:
            for field in fields:
                series = bbg_cache.get_prices(ticker, start, end, field)
                if series is not None:
                    for dt, val in series.items():
                        rows.append({"ticker": ticker, "date": dt, field: val})
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index(["date", "ticker"])
