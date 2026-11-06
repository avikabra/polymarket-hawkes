"""Step 6: live liquidity. Dollars and shares traded per contract per Eastern-time day.

Built from the pulled trades, clipped to each rung's start through its actual end. A contract
is liquid on day D when its cumulative dollars through D reach a floor, which a trader watching
the market on D could compute. Entry point: scripts/ingest/03b_daily_volume.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ET = "America/New_York"
COLUMNS = ["condition_id", "day", "dollars", "shares", "cum_dollars"]


def build_daily_volume(trades_root: str | Path, markets: pd.DataFrame) -> pd.DataFrame:
    """One row per (condition_id, ET day with trades). `cum_dollars` runs through that day."""
    window = markets.set_index("condition_id")[["start_ts_utc", "end_ts_utc"]]
    parts = []
    for p in sorted(Path(trades_root).glob("contract_type=*/year=*/month=*/part-*.parquet")):
        df = pd.read_parquet(p, columns=["market_id", "ts_s", "size_usdc", "size_shares"])
        if df["size_shares"].isna().any():
            raise ValueError(f"{p} has no size_shares; rerun scripts/ingest/03_pull_trades.py")
        cid = df["market_id"].iat[0]
        if cid not in window.index:
            continue
        lo, hi = (int(window.at[cid, c].timestamp()) for c in ("start_ts_utc", "end_ts_utc"))
        df = df[(df["ts_s"] >= lo) & (df["ts_s"] <= hi)]
        if df.empty:
            continue
        day = pd.to_datetime(df["ts_s"], unit="s", utc=True).dt.tz_convert(ET).dt.date
        g = df.groupby(day).agg(dollars=("size_usdc", "sum"), shares=("size_shares", "sum"))
        parts.append(g.rename_axis("day").reset_index().assign(condition_id=cid))
    if not parts:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.concat(parts, ignore_index=True).sort_values(["condition_id", "day"]).reset_index(drop=True)
    out["cum_dollars"] = out.groupby("condition_id")["dollars"].cumsum()
    return out[COLUMNS]
