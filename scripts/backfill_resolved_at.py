"""One-off utility: backfill resolved_at into an existing universe.parquet.

Context: src/polymarket/gamma.py's resolved_at field mapping was fixed
(was reading resolutionDate/resolvedDate, which don't exist in Gamma's API;
the real field is closedTime). Re-running scripts/01_discover_universe.py's
full day-sliced rediscovery to pick up the fix is prohibitively slow (~6h+ —
each day-slice pages all the way to Gamma's ~2,100-offset ceiling on
closed=true markets, confirmed against the live API 2026-09-29, because
daily closed-market volume genuinely exceeds it on busy days).

This script is much faster: it looks up the *existing* universe's known
market_ids (conditionIds) directly via GammaClient.get_markets_by_condition_ids
(batched), rather than rediscovering the whole universe from scratch. Patches
only the resolved_at column; every other column (market_id, end_at, category,
contract_family, etc.) is left untouched.

Usage:
    uv run python scripts/backfill_resolved_at.py \
        --in data/polymarket/universe.parquet.bak_preresolvedat \
        --out data/polymarket/universe.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio

import pandas as pd

from src.polymarket.gamma import GammaClient, _parse_dt
from src.utils import get_logger

log = get_logger(__name__)

BATCH_SIZE = 50


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill resolved_at from Gamma's closedTime.")
    p.add_argument("--in", dest="in_path", default="data/polymarket/universe.parquet.bak_preresolvedat")
    p.add_argument("--out", dest="out_path", default="data/polymarket/universe.parquet")
    return p.parse_args()


async def _fetch_all(condition_ids: list[str]) -> dict[str, str | None]:
    """Return {condition_id: closedTime_raw_or_None} for every id, batched."""
    client = GammaClient()
    result: dict[str, str | None] = {}
    n = len(condition_ids)
    for i in range(0, n, BATCH_SIZE):
        batch = condition_ids[i : i + BATCH_SIZE]
        for closed in (True, False):
            markets = await client.get_markets_by_condition_ids(batch, closed=closed)
            for m in markets:
                cid = m.get("conditionId")
                if cid:
                    result[cid] = m.get("closedTime")
        log.info(
            "backfill_resolved_at",
            progress=f"{min(i + BATCH_SIZE, n)}/{n}",
            found_so_far=len(result),
        )
    return result


def main() -> None:
    args = _parse_args()
    df = pd.read_parquet(args.in_path)
    condition_ids = df["market_id"].astype(str).tolist()
    log.info("backfill_resolved_at", n_markets=len(condition_ids))

    closed_time_map = asyncio.run(_fetch_all(condition_ids))

    n_found = sum(1 for v in closed_time_map.values() if v)
    log.info(
        "backfill_resolved_at",
        n_markets=len(condition_ids),
        n_matched=len(closed_time_map),
        n_with_closed_time=n_found,
    )

    def _resolve(mid: str):
        raw = closed_time_map.get(mid)
        parsed = _parse_dt(raw) if raw else None
        return parsed

    df["resolved_at"] = df["market_id"].astype(str).map(_resolve)
    df["resolved_at"] = pd.to_datetime(df["resolved_at"], utc=True)

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    n_populated = df["resolved_at"].notna().sum()
    print(f"Written {len(df)} rows -> {out_path}")
    print(f"resolved_at populated: {n_populated}/{len(df)} ({100*n_populated/len(df):.1f}%)")


if __name__ == "__main__":
    main()
