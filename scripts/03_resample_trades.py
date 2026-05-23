"""Script 03: Resample trade fills to 1-minute OHLCV bars and register DuckDB views."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

from src.polymarket.resampler import resample_to_1min
from src.schemas import Trade
from src.utils import get_connection, get_logger, register_parquet_views

log = get_logger(__name__)


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    paths = _load_yaml("config/paths.yaml")
    universe = pd.read_parquet(paths["polymarket"]["universe"]).set_index("market_id")

    trades_root = Path(paths["polymarket"]["trades"])
    bars_root = Path(paths["polymarket"]["bars_1min"])

    trade_files = sorted(trades_root.rglob("part-*.parquet"))
    total_bars = 0
    markets_processed = 0

    for parquet_file in tqdm(trade_files, desc="Markets"):
        market_id = parquet_file.stem.removeprefix("part-")

        if market_id not in universe.index:
            log.warning("market not in universe", extra={"market_id": market_id})
            continue

        row = universe.loc[market_id]
        market_open_ts = int(pd.Timestamp(row["created_at"]).timestamp())
        market_close_ts = int(pd.Timestamp(row["end_at"]).timestamp())
        category = row["category"]
        end_dt = pd.Timestamp(row["end_at"])
        year, month = end_dt.year, end_dt.month

        df = pd.read_parquet(parquet_file)
        trades = [Trade(**r) for r in df.to_dict("records")]

        bars = resample_to_1min(trades, market_open_ts, market_close_ts)

        out_path = (
            bars_root
            / f"category={category}/year={year}/month={month:02d}/part-{market_id}.parquet"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(pd.DataFrame(bars)), out_path)

        total_bars += len(bars)
        markets_processed += 1

    print(f"\nMarkets processed: {markets_processed}")
    print(f"Total 1-min bars written: {total_bars}")

    conn = get_connection()
    register_parquet_views(conn, paths)
    conn.close()

    success = bars_root / "_SUCCESS"
    bars_root.mkdir(parents=True, exist_ok=True)
    success.touch()
    log.info("done", extra={"markets": markets_processed, "total_bars": total_bars})


if __name__ == "__main__":
    main()
