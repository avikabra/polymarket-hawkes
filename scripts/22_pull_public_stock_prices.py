"""Script 22: pull real public stock prices for the companies in our universe.

Context (2026-10-14): every result reported so far compares Polymarket against
itself -- the matching score vs. Polymarket's own realized price move; the
prediction models vs. Polymarket's own reaction. None of it checks whether the
real, publicly-traded company also reacted, or whether Polymarket's reaction is
proportionate to that. This script pulls the real daily closes needed to make
that comparison (scripts/23_benchmark_vs_public_market.py does the join).

Ticker source: data/polymarket/universe.parquet's own `ticker` column, which is
populated for 67/86 companies by the existing classifier (src/polymarket/
company_filter.py). The other 19 split into two real categories, found while
building this:
  - 7 are genuinely private (no public stock exists): OpenAI, Anthropic, xAI,
    SpaceX, Databricks, Stripe, Klarna. Excluded from the benchmark, not a bug.
  - 12 are real, large public companies the classifier's COMPANY_DICT simply
    never had a ticker alias for (Boeing, Goldman Sachs, Citigroup, Morgan
    Stanley, GM, Ford, Mastercard, AMC, Home Depot, HP, Visa, Block) -- a real
    classifier gap. Patched here as a standalone override, NOT in
    company_filter.py itself: Visa's real ticker is a single letter ("V") and
    Citigroup's is one letter ("C"), and this codebase's GDELT-matching logic
    (gdelt_entity_aliases) only treats 2-5 character aliases as ticker-shaped
    for exclusion from the text-matching regex -- adding single-letter tickers
    there would leak "V"/"C" into the entity regex and risk corrupting the
    already-validated Thread 1 matching pipeline if it's ever rerun. Keeping
    this override local to the stock pull avoids that risk entirely.

Two more real classifier bugs found on the first real pull (2026-10-14):
universe.parquet's `ticker` column held the literal company name instead of a
real ticker for AT&T ("AT&T" -> real ticker "T") and TSMC ("TSMC" -> real ADR
ticker "TSM"), same single-letter issue as Visa/Citigroup for AT&T, so also
kept local rather than patched into company_filter.py. One real, separate
gap: Warner Bros Discovery's real ticker (WBD) returns almost no history from
this source (`yf.Ticker("WBD").history(period="max")` gives exactly one row,
2026-10-05) -- consistent with WBD's real corporate split executing just
before this pull, not a bug here. Excluded from the benchmark as a genuine,
very recent data gap rather than guessing at a successor ticker.

Writes: data/stocks/daily_prices.parquet (company_id, ticker, date, close,
adj_close), data/stocks/ticker_coverage.json (which companies got real data,
which were skipped and why).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.marketdata.yahoo import YahooClient
from src.utils import get_logger

UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
OUT_DIR = Path("data/stocks")
PRICES_PATH = OUT_DIR / "daily_prices.parquet"
COVERAGE_PATH = OUT_DIR / "ticker_coverage.json"

log = get_logger(__name__)

# Buffer a little beyond the real universe's resolution-date range
# (2024-03-21 to 2026-08-27, per reports/novel_math_design.md) so every
# article's +24h window has a stock price on both sides.
START = datetime(2024, 3, 1, tzinfo=timezone.utc)
END = datetime(2026, 9, 15, tzinfo=timezone.utc)

# Genuinely private companies -- no public stock exists. Not a gap to fix.
_PRIVATE_COMPANY_IDS = {
    "openai", "anthropic", "xai", "spacex", "databricks", "stripe", "klarna",
}

# Real, very recent data gap (see module docstring): WBD's history is gone
# from this source as of the 2026-10-14 pull, consistent with its corporate
# split executing days earlier. Excluded rather than guessing a successor
# ticker.
_EXCLUDED_RECENT_CORPORATE_ACTION_IDS = {"warner_bros"}

# Real public companies missing a ticker in company_filter.py's COMPANY_DICT
# (see module docstring for why this is NOT patched there). ticker_candidates
# is a list tried in order; results are merged so an early ticker rename
# (Block: SQ -> XYZ in 2025) doesn't silently lose the earlier period.
_TICKER_OVERRIDE: dict[str, list[str]] = {
    "boeing": ["BA"],
    "goldman_sachs": ["GS"],
    "citigroup": ["C"],
    "morgan_stanley": ["MS"],
    "gm": ["GM"],
    "ford": ["F"],
    "mastercard": ["MA"],
    "amc": ["AMC"],
    "home_depot": ["HD"],
    "hp": ["HPQ"],
    "visa": ["V"],
    "block": ["XYZ", "SQ"],  # renamed 2025; try both, merge by date
    "at&t": ["T"],
    "tsmc": ["TSM"],
}


def _build_ticker_map(universe_df: pd.DataFrame) -> dict[str, list[str]]:
    """company_id -> list of tickers to try, in order."""
    companies = universe_df[["company_id", "ticker"]].drop_duplicates(subset=["company_id"])
    ticker_map: dict[str, list[str]] = {}
    for _, row in companies.iterrows():
        cid = str(row["company_id"])
        if cid in _PRIVATE_COMPANY_IDS or cid in _EXCLUDED_RECENT_CORPORATE_ACTION_IDS:
            continue
        if cid in _TICKER_OVERRIDE:
            ticker_map[cid] = _TICKER_OVERRIDE[cid]
        elif row["ticker"] and pd.notna(row["ticker"]):
            ticker_map[cid] = [str(row["ticker"])]
        else:
            log.warning("no_ticker_unaccounted", company_id=cid)
    return ticker_map


def _pull_all(ticker_map: dict[str, list[str]]) -> tuple[pd.DataFrame, dict]:
    client = YahooClient()
    all_rows: list[pd.DataFrame] = []
    coverage: dict[str, dict] = {}

    for company_id, tickers in ticker_map.items():
        merged: pd.DataFrame | None = None
        used_tickers = []
        for ticker in tickers:
            df = client.get_daily_closes(ticker, START, END)
            time.sleep(1.0)  # polite spacing; yfinance isn't IP-blocked but no need to hammer it
            if df.empty:
                continue
            used_tickers.append(ticker)
            if merged is None:
                merged = df
            else:
                # Prefer the first (primary) ticker's rows; fill gaps from fallback.
                existing_dates = set(merged["date"])
                extra = df[~df["date"].isin(existing_dates)]
                merged = pd.concat([merged, extra], ignore_index=True)

        if merged is None or merged.empty:
            coverage[company_id] = {"status": "no_data", "tickers_tried": tickers}
            log.warning("no_stock_data", company_id=company_id, tickers=tickers)
            continue

        merged["company_id"] = company_id
        merged["ticker"] = "+".join(used_tickers)
        all_rows.append(merged)
        coverage[company_id] = {
            "status": "ok",
            "tickers_used": used_tickers,
            "rows": len(merged),
            "first_date": merged["date"].min(),
            "last_date": merged["date"].max(),
        }

    prices_df = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    return prices_df, coverage


def main() -> None:
    if not UNIVERSE_PATH.exists():
        print(f"{UNIVERSE_PATH} not found.")
        return

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    ticker_map = _build_ticker_map(universe_df)
    log.info(
        "ticker_map_built",
        n_companies=universe_df["company_id"].nunique(),
        n_with_ticker=len(ticker_map),
        n_private=len(_PRIVATE_COMPANY_IDS),
    )

    prices_df, coverage = _pull_all(ticker_map)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prices_df.to_parquet(PRICES_PATH, index=False)
    coverage["_private_company_ids"] = sorted(_PRIVATE_COMPANY_IDS)
    coverage["_excluded_recent_corporate_action_ids"] = sorted(_EXCLUDED_RECENT_CORPORATE_ACTION_IDS)
    with open(COVERAGE_PATH, "w") as f:
        json.dump(coverage, f, indent=2, default=str)

    n_ok = sum(1 for v in coverage.values() if isinstance(v, dict) and v.get("status") == "ok")
    print(f"Companies with ticker to try: {len(ticker_map)}")
    print(f"Companies with real stock data: {n_ok}")
    print(f"Companies excluded as private: {len(_PRIVATE_COMPANY_IDS)}")
    print(f"Written: {PRICES_PATH} ({len(prices_df)} rows)")
    print(f"Written: {COVERAGE_PATH}")


if __name__ == "__main__":
    main()
