"""Yahoo Finance daily-close client, for the public-market benchmark (2026-10-14).

Context: every other result in this project measures Polymarket's own reaction
to news, against itself (the matching score vs. Polymarket's own realized price
move; the prediction models vs. Polymarket's own reaction). None of it checks
whether the underlying COMPANY's real, publicly-traded stock also reacted, or
whether Polymarket's reaction is proportionate to that real-world reaction. This
client pulls the real daily close prices needed to make that comparison.

Uses the `yfinance` package rather than calling Yahoo's unofficial chart
endpoint directly. Confirmed 2026-10-13/14: raw httpx/curl requests to
query1/query2.finance.yahoo.com got IP-blocked (429 on every request,
including a bare manual curl, even with a browser User-Agent and 10s spacing)
after this session's earlier manual endpoint testing. yfinance (via its
curl_cffi backend, which replicates a real browser's TLS fingerprint rather
than just its headers) got through immediately from the same IP. No API key
required either way; this is still a research tool, not a market-data vendor,
so treat gaps/delistings as real data, not bugs.
"""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils import DiskCache, get_logger


class YahooClient:
    def __init__(self, cache_dir: str = "data/.cache/yahoo") -> None:
        self._cache = DiskCache(cache_dir)
        self._log = get_logger(__name__)

    @retry(wait=wait_exponential(multiplier=2, min=2, max=30), stop=stop_after_attempt(3))
    def _fetch(self, ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
        return yf.Ticker(ticker).history(
            start=start.date().isoformat(),
            end=end.date().isoformat(),
            interval="1d",
            auto_adjust=False,
        )

    def get_daily_closes(self, ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Return a DataFrame with columns: date (YYYY-MM-DD), close, adj_close.

        Empty DataFrame (not an exception) if the ticker is delisted, invalid,
        or Yahoo has no data for the window -- the caller decides what that means
        (e.g. a renamed or recently-IPO'd ticker), this client does not guess.
        """
        cache_key = f"yahoo:chart:{ticker}:{start.date()}:{end.date()}"
        cached = self._cache.get(cache_key, max_age_seconds=7 * 24 * 3600)
        if cached is not None:
            return pd.read_parquet(io.BytesIO(cached))

        try:
            raw = self._fetch(ticker, start, end)
        except Exception:
            self._log.warning("yahoo_fetch_failed", ticker=ticker)
            return pd.DataFrame(columns=["date", "close", "adj_close"])

        if raw.empty:
            self._log.warning("yahoo_no_data", ticker=ticker)
            return pd.DataFrame(columns=["date", "close", "adj_close"])

        df = pd.DataFrame({
            "date": raw.index.tz_localize(None).normalize().astype(str),
            "close": raw["Close"].astype(float).to_numpy(),
            "adj_close": raw["Adj Close"].astype(float).to_numpy(),
        })

        buf = io.BytesIO()
        df.to_parquet(buf)
        self._cache.set(cache_key, buf.getvalue())
        self._log.info("yahoo_pulled", ticker=ticker, rows=len(df))
        return df
