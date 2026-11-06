"""Steps 3 to 11: pull, type, date and check every closed contract of the 61 companies.

Writes data/polymarket/contracts/{markets,events,checks}.parquet and pull_report.md.
markets.parquet keeps every rung with `excluded_reason` (null = kept). Outcomes exclude
nothing: the step 10 checks only report. The close check needs daily closing prices, pulled
here from Yahoo for the companies with close-type contracts and cached in
data/stocks/closes.parquet. Split events for all companies come from Yahoo too
(data/stocks/splits.parquet) and set each price rung's usable end.

    uv run python scripts/ingest/02_pull_contracts.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import asyncio
from datetime import datetime

import pandas as pd
import yaml

from src.ingest.companies import load_companies
from src.ingest.contracts import (
    CLOSE_BUCKET, CLOSE_LADDER, apply_splits, build_events, build_markets,
    build_report, check_closes, check_ladders, pull_events,
)
from src.marketdata.yahoo import YahooClient
from src.polymarket.gamma import GammaClient


def pull_closes(mk: pd.DataFrame, tickers: dict[str, str], path: Path) -> pd.DataFrame:
    need = mk[mk["excluded_reason"].isna() & mk["contract_type"].isin([CLOSE_LADDER, CLOSE_BUCKET])]
    start = datetime.fromisoformat(str(need["end_et"].min().date()))
    end = datetime.fromisoformat(str((need["end_et"].max() + pd.Timedelta(days=2)).date()))
    yc = YahooClient()
    parts = []
    for cid in sorted(need["company_id"].unique()):
        df = yc.get_daily_closes(tickers[cid], start, end)
        if df.empty:
            print(f"no closes for {cid} ({tickers[cid]}); its close checks stay unchecked")
        parts.append(df.assign(company_id=cid, ticker=tickers[cid]))
    closes = pd.concat(parts, ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    closes.to_parquet(path, index=False)
    return closes


def pull_splits(tickers: dict[str, str], start: str, end: str, path: Path) -> pd.DataFrame:
    """Split events of every company. A failed Yahoo fetch raises; a company with no data is listed."""
    yc = YahooClient()
    parts, nodata = [], []
    for cid, tk in sorted(tickers.items()):
        df = yc.get_splits(tk, datetime.fromisoformat(start), datetime.fromisoformat(end))
        if df.empty and yc.get_daily_closes(tk, datetime.fromisoformat(start), datetime.fromisoformat(end)).empty:
            nodata.append(cid)
        parts.append(df.assign(company_id=cid, ticker=tk))
    splits = pd.concat(parts, ignore_index=True)[["company_id", "ticker", "date", "ratio"]]
    path.parent.mkdir(parents=True, exist_ok=True)
    splits.to_parquet(path, index=False)
    print(f"{len(tickers)} companies checked for splits: {len(splits)} splits "
          f"({splits['company_id'].nunique()} companies); no Yahoo data: {nodata or 'none'}")
    return splits


async def main() -> None:
    cfg = yaml.safe_load(open("config/contracts.yaml"))
    out = Path(cfg["paths"]["out_dir"])
    out.mkdir(parents=True, exist_ok=True)
    companies = load_companies()

    client = GammaClient(requests_per_second=cfg["rate_limit"]["requests_per_second"])
    events = await pull_events(client, companies, cfg["end_max"])
    mk = build_markets(events, cfg)
    splits = pull_splits({c.id: c.ticker for c in companies}, cfg["splits_from"],
                         str((pd.Timestamp(cfg["end_max"]) + pd.Timedelta(days=1)).date()), Path(cfg["paths"]["splits"]))
    mk = apply_splits(mk, splits)

    closes = pull_closes(mk, {c.id: c.ticker for c in companies}, Path(cfg["paths"]["closes"]))
    ladder, close = check_ladders(mk), check_closes(mk, closes)
    ev = build_events(mk)

    mk.to_parquet(out / "markets.parquet", index=False)
    ev.to_parquet(out / "events.parquet", index=False)
    pd.concat([ladder, close]).to_parquet(out / "checks.parquet", index=False)
    (out / "pull_report.md").write_text(build_report(mk, ev, ladder, close))
    print(f"{len(mk)} rungs pulled, {int(mk['excluded_reason'].isna().sum())} kept in {len(ev)} groups -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
