"""Script 02: Pull on-chain trade fills for focal markets via Goldsky."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import statistics
from datetime import datetime, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from tqdm import tqdm

from src.polymarket.dataapi import DataApiClient, normalize_dataapi_fill
from src.polymarket.trades import sort_trades
from src.schemas import Trade
from src.utils import get_logger

log = get_logger(__name__)


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _to_parquet(trades: list[Trade], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = [t.model_dump() for t in trades]
    df = pd.DataFrame(records)
    pq.write_table(pa.Table.from_pandas(df), out_path)


async def main() -> None:
    focal = _load_yaml("config/focal.yaml")["focal"]
    universe = pd.read_parquet("data/polymarket/universe.parquet")
    primary = universe[universe["is_primary_sample"] == True]
    if len(primary) == 0:
        raise RuntimeError(
            "no primary-sample markets in universe.parquet — cannot pull trades; "
            "re-run script 01"
        )
    # Zero lifetime volume => no taker trades exist; skip to avoid pointless requests.
    primary = primary[primary["total_volume_usdc"].fillna(0) > 0]
    log.info("pulling trades", extra={"markets_with_volume": len(primary)})

    # W7-9: trade source swapped Goldsky (deprecated) -> Polymarket Data-API.
    # The Data-API windows on trade timestamps; bound each market by its own life.
    now_ts = int(datetime.now(timezone.utc).timestamp())

    client = DataApiClient()
    total_trades = 0
    trades_per_market: list[int] = []
    empty_but_liquid: list[str] = []

    skipped = 0
    for _, row in tqdm(primary.iterrows(), total=len(primary), desc="Markets"):
        market_id = row["market_id"]
        yes_token_id = row["yes_token_id"]
        contract_family = row["contract_family"]
        end_dt = pd.Timestamp(row["end_at"])
        year, month = end_dt.year, end_dt.month
        out_path = Path(
            f"data/polymarket/trades/contract_family={contract_family}"
            f"/year={year}/month={month:02d}/part-{market_id}.parquet"
        )

        # Durable resume: a written part is a completed market — skip the network entirely.
        if out_path.exists():
            n = len(pd.read_parquet(out_path, columns=["ts_s"]))
            total_trades += n
            trades_per_market.append(n)
            skipped += 1
            continue

        # Stable, order-agnostic per-market window. Some markets have a corrupt
        # created_at (== scrape date, after end_at), which would invert the window and
        # silently drop all trades; min/max keeps it valid regardless. Fixed bounds
        # (no now()) keep DiskCache keys identical across runs so resumes reuse cache.
        c_ts = int(pd.Timestamp(row["created_at"]).timestamp())
        e_ts = int(end_dt.timestamp())
        start_ts = min(c_ts, e_ts) - 86400
        end_ts = max(c_ts, e_ts) + 14 * 86400

        # One call per conditionId returns both YES and NO fills. Errors propagate
        # (fail loud) — the client already retries transient failures internally.
        trades: list[Trade] = []
        async for fill in client.iter_market_fills(market_id, start_ts, end_ts):
            trade = normalize_dataapi_fill(fill, market_id=market_id, yes_token_id=yes_token_id)
            if trade is not None:
                trades.append(trade)

        trades = sort_trades(trades)

        if trades:
            _to_parquet(trades, out_path)
        elif float(row["total_volume_usdc"]) > 0:
            # Loud: a market with lifetime volume must return at least one trade.
            empty_but_liquid.append(market_id)

        total_trades += len(trades)
        trades_per_market.append(len(trades))

    log.info("pull loop done", extra={"skipped_already_pulled": skipped})

    median_trades = statistics.median(trades_per_market) if trades_per_market else 0
    print(f"\nMarkets processed: {len(trades_per_market)}")
    print(f"Total trades: {total_trades}")
    print(f"Median trades per market: {median_trades:.0f}")

    if empty_but_liquid:
        raise RuntimeError(
            f"FATAL: {len(empty_but_liquid)} markets have total_volume_usdc > 0 but "
            f"returned 0 trades — Data-API pull is incomplete. _SUCCESS will NOT be "
            f"written. First few: {empty_but_liquid[:5]}"
        )

    if total_trades == 0:
        raise RuntimeError(
            "FATAL: 0 trades returned across all markets — Data-API query is broken "
            "or all condition IDs are wrong. _SUCCESS will NOT be written."
        )

    success = Path("data/polymarket/trades/_SUCCESS")
    success.parent.mkdir(parents=True, exist_ok=True)
    success.touch()
    log.info("done", extra={"markets": len(trades_per_market), "total_trades": total_trades})


if __name__ == "__main__":
    asyncio.run(main())
