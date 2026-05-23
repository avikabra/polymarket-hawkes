"""Script 01: Discover the focal market universe from Gamma API."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
from collections import defaultdict
from itertools import combinations

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.polymarket.gamma import GammaClient
from src.schemas import Market
from src.utils import get_logger

log = get_logger(__name__)


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _overlap_fraction(m1: Market, m2: Market) -> float:
    overlap_start = max(m1.created_at, m2.created_at)
    overlap_end = min(m1.end_at, m2.end_at)
    overlap_secs = max(0.0, (overlap_end - overlap_start).total_seconds())
    dur1 = (m1.end_at - m1.created_at).total_seconds()
    dur2 = (m2.end_at - m2.created_at).total_seconds()
    shorter = min(dur1, dur2)
    return overlap_secs / shorter if shorter > 0 else 0.0


def _link_correlated(markets: list[Market]) -> list[Market]:
    by_cat: dict[str, list[Market]] = defaultdict(list)
    for m in markets:
        by_cat[m.category].append(m)

    updated = {m.market_id: m for m in markets}
    for cat_markets in by_cat.values():
        for m1, m2 in combinations(cat_markets, 2):
            if _overlap_fraction(m1, m2) > 0.5:
                dur1 = (m1.end_at - m1.created_at).total_seconds()
                dur2 = (m2.end_at - m2.created_at).total_seconds()
                shorter, longer = (m1, m2) if dur1 < dur2 else (m2, m1)
                if updated[shorter.market_id].parent_event_id is None:
                    updated[shorter.market_id] = shorter.model_copy(
                        update={"parent_event_id": longer.market_id}
                    )
    return list(updated.values())


def _to_parquet(markets: list[Market], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not markets:
        pq.write_table(pa.table({}), out_path)
        return
    records = []
    for m in markets:
        d = m.model_dump()
        d["tags"] = json.dumps(d["tags"])
        records.append(d)
    df = pd.DataFrame(records)
    for col in ["created_at", "end_at", "resolved_at"]:
        df[col] = pd.to_datetime(df[col], utc=True)
    pq.write_table(pa.Table.from_pandas(df), out_path)


async def main() -> None:
    focal = _load_yaml("config/focal.yaml")["focal"]
    categories = _load_yaml("config/categories.yaml")["categories"]

    client = GammaClient()
    raw_by_id: dict[str, dict] = {}
    cat_by_id: dict[str, str] = {}

    for cat_name in focal["categories"]:
        cat_cfg = categories.get(cat_name, {})
        for tag in cat_cfg.get("polymarket_tags", []):
            log.info("fetching", extra={"category": cat_name, "tag": tag})
            try:
                page = await client.list_markets(
                    tag=tag,
                    closed=True,
                    start_after=focal.get("start_date"),
                    end_before=focal.get("end_date"),
                )
            except Exception as exc:
                log.warning("fetch failed", extra={"tag": tag, "error": str(exc)})
                continue
            for raw in page:
                cid = raw.get("conditionId", "")
                if cid and cid not in raw_by_id:
                    raw_by_id[cid] = raw
                    cat_by_id[cid] = cat_name

    markets: list[Market] = []
    for cid, raw in raw_by_id.items():
        try:
            m = client.parse_market(raw, category=cat_by_id[cid])
        except Exception as exc:
            log.warning("parse failed", extra={"condition_id": cid, "error": str(exc)})
            continue
        dur_days = (m.end_at - m.created_at).days
        if m.total_volume_usdc < focal["min_volume_usdc"]:
            continue
        if dur_days < focal["min_market_duration_days"]:
            continue
        markets.append(m)

    markets = _link_correlated(markets)
    _to_parquet(markets, Path("data/polymarket/universe.parquet"))

    primary_types = set(focal["market_types"]["primary"])
    by_cat: dict[str, dict] = defaultdict(lambda: {"total": 0, "primary": 0, "secondary": 0})
    for m in markets:
        by_cat[m.category]["total"] += 1
        if m.market_type in primary_types:
            by_cat[m.category]["primary"] += 1
        else:
            by_cat[m.category]["secondary"] += 1

    print(f"\n{'category':<14} {'total':>6} {'primary':>8} {'secondary':>10}")
    print("-" * 42)
    for cat, counts in sorted(by_cat.items()):
        print(f"{cat:<14} {counts['total']:>6} {counts['primary']:>8} {counts['secondary']:>10}")
    print(f"\nTotal markets: {len(markets)}")

    Path("data/polymarket/_UNIVERSE_SUCCESS").touch()
    log.info("done", extra={"n_markets": len(markets)})


if __name__ == "__main__":
    asyncio.run(main())
