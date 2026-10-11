"""One-off utility: backfill parent_event_id into an existing universe.parquet.

Context: src/polymarket/gamma.py's parse_market hardcoded parent_event_id=None.
Fixed 2026-10-10 -- every /markets response already carries a real "events" array
(each market's parent Polymarket Event, with a stable numeric id), confirmed by
fetching live markets and inspecting raw keys directly. This field is what
scripts/21_hypothesis_tests.py's block bootstrap clusters by; with it 100% null,
every bootstrap resample reconstructed the identical dataset (one giant cluster),
producing degenerate zero-width confidence intervals -- see reports/novel_math_design.md.

Same approach as scripts/backfill_resolved_at.py: look up the *existing* universe's
known market_ids (conditionIds) directly via GammaClient.get_markets_by_condition_ids
(batched), rather than rediscovering the whole universe from scratch. Patches only
the parent_event_id column; every other column is left untouched. Expect partial
coverage, same as the resolved_at backfill (~40%) -- report the real rate honestly,
don't assume full coverage.

Usage:
    uv run python scripts/backfill_parent_event_id.py \
        --in data/polymarket/universe.parquet \
        --out data/polymarket/universe.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio

import pandas as pd

from src.polymarket.gamma import GammaClient
from src.utils import get_logger

log = get_logger(__name__)

BATCH_SIZE = 50


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill parent_event_id from Gamma's events[0].id.")
    p.add_argument("--in", dest="in_path", default="data/polymarket/universe.parquet")
    p.add_argument("--out", dest="out_path", default="data/polymarket/universe.parquet")
    return p.parse_args()


async def _fetch_all(condition_ids: list[str]) -> dict[str, str | None]:
    """Return {condition_id: parent_event_id_or_None} for every id, batched."""
    client = GammaClient()
    result: dict[str, str | None] = {}
    n = len(condition_ids)
    for i in range(0, n, BATCH_SIZE):
        batch = condition_ids[i : i + BATCH_SIZE]
        for closed in (True, False):
            markets = await client.get_markets_by_condition_ids(batch, closed=closed)
            for m in markets:
                cid = m.get("conditionId")
                events = m.get("events") or []
                if cid and events:
                    result[cid] = str(events[0]["id"])
        log.info(
            "backfill_parent_event_id",
            progress=f"{min(i + BATCH_SIZE, n)}/{n}",
            found_so_far=len(result),
        )
    return result


def main() -> None:
    args = _parse_args()
    df = pd.read_parquet(args.in_path)
    condition_ids = df["market_id"].astype(str).tolist()
    log.info("backfill_parent_event_id", n_markets=len(condition_ids))

    event_id_map = asyncio.run(_fetch_all(condition_ids))

    log.info(
        "backfill_parent_event_id",
        n_markets=len(condition_ids),
        n_matched=len(event_id_map),
    )

    df["parent_event_id"] = df["market_id"].astype(str).map(event_id_map)

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    n_populated = df["parent_event_id"].notna().sum()
    n_unique_events = df["parent_event_id"].nunique(dropna=True)
    print(f"Written {len(df)} rows -> {out_path}")
    print(f"parent_event_id populated: {n_populated}/{len(df)} ({100*n_populated/len(df):.1f}%)")
    print(f"unique parent events among populated rows: {n_unique_events}")


if __name__ == "__main__":
    main()
