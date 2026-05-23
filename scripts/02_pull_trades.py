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

from src.polymarket.goldsky import GoldskyClient
from src.polymarket.trades import normalize_fill, sort_trades
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

    start_ts = int(
        datetime.fromisoformat(focal["start_date"]).replace(tzinfo=timezone.utc).timestamp()
    )
    end_ts = int(
        datetime.fromisoformat(focal["end_date"]).replace(tzinfo=timezone.utc).timestamp()
    )

    client = GoldskyClient()
    total_trades = 0
    trades_per_market: list[int] = []

    for _, row in tqdm(primary.iterrows(), total=len(primary), desc="Markets"):
        market_id = row["market_id"]
        yes_token_id = row["yes_token_id"]
        no_token_id = row["no_token_id"]
        category = row["category"]
        end_dt = pd.Timestamp(row["end_at"])
        year, month = end_dt.year, end_dt.month

        fills_raw: dict[str, dict] = {}
        for token_id in filter(None, [yes_token_id, no_token_id]):
            try:
                async for fill in client.iter_fills(token_id, start_ts, end_ts):
                    key = f"{fill['transactionHash']}:{fill['logIndex']}"
                    fills_raw.setdefault(key, fill)
            except Exception as exc:
                log.warning(
                    "fill fetch failed",
                    extra={"market_id": market_id, "token_id": token_id, "error": str(exc)},
                )

        trades: list[Trade] = []
        for fill in fills_raw.values():
            trade = normalize_fill(fill, market_id=market_id, yes_token_id=yes_token_id)
            if trade is not None:
                trades.append(trade)

        trades = sort_trades(trades)

        if trades:
            out_path = Path(
                f"data/polymarket/trades/category={category}"
                f"/year={year}/month={month:02d}/part-{market_id}.parquet"
            )
            _to_parquet(trades, out_path)

        total_trades += len(trades)
        trades_per_market.append(len(trades))

    median_trades = statistics.median(trades_per_market) if trades_per_market else 0
    print(f"\nMarkets processed: {len(trades_per_market)}")
    print(f"Total trades: {total_trades}")
    print(f"Median trades per market: {median_trades:.0f}")

    success = Path("data/polymarket/trades/_SUCCESS")
    success.parent.mkdir(parents=True, exist_ok=True)
    success.touch()
    log.info("done", extra={"markets": len(trades_per_market), "total_trades": total_trades})


if __name__ == "__main__":
    asyncio.run(main())
