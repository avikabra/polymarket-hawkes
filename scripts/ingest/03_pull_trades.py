"""Pull the trade history of every non-excluded rung that traded at all.

No lifetime or liquidity cut: liquidity is judged day by day from these trades (03b). Each
trade is recorded to the second, converted to log-odds, and clipped to the rung's start through
its actual end (the settlement time for a touched barrier). Reads
data/polymarket/contracts/markets.parquet. Output is partitioned
data/polymarket/trades/contract_type=<t>/year=<Y>/month=<M>/part-<condition_id>.parquet
(Trade.market_id is the conditionId). Log-odds invariant: price_raw is clipped to
(0.001, 0.999) inside normalize_dataapi_fill before conversion.

Resume: a part file already on disk is reused. A reused file is clipped to the rung's window,
and a file from before `size_shares` existed gets it from size_usdc / the traded token's own
price when no price was clipped, and is pulled again otherwise (the page cache makes that cheap).
Markets with volume but no trades in the window are listed in <trades>/_no_trades.csv.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import asyncio

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

import yaml
from src.polymarket.dataapi import DataApiClient, normalize_dataapi_fill
from src.polymarket.trades import sort_trades
from src.utils import get_logger

log = get_logger(__name__)
PART = "contract_type=*/year=*/month=*/part-*.parquet"


def reuse(path: Path, start_ts: int, end_ts: int, yes_token_id: str) -> bool:
    """Make an existing part file satisfy the current window and schema. False means pull again."""
    df = pq.read_table(path).to_pandas()
    if "size_shares" not in df or df["size_shares"].isna().any():
        if ((df["price_raw"] <= 0.001) | (df["price_raw"] >= 0.999)).any():
            return False  # a clipped price hides the true token price
        own = df["price_raw"].where(df["token_id"] == yes_token_id, 1.0 - df["price_raw"])
        df["size_shares"] = df["size_usdc"] / own
    keep = df[(df["ts_s"] >= start_ts) & (df["ts_s"] < end_ts)]
    if len(keep) == len(df) and "size_shares" in pq.read_schema(path).names:
        return True
    if keep.empty:
        return False
    pq.write_table(pa.Table.from_pandas(keep.reset_index(drop=True)), path)
    return True


async def main() -> None:
    cfg = yaml.safe_load(open("config/contracts.yaml"))
    mk = pd.read_parquet(Path(cfg["paths"]["out_dir"]) / "markets.parquet")
    todo = mk[mk["excluded_reason"].isna() & mk["yes_token_id"].notna() & (mk["volume_shares"] > 0)]
    log.info("pulling trades", markets=len(todo), kept=int(mk["excluded_reason"].isna().sum()), of=len(mk))
    root = Path(cfg["paths"]["trades"])
    have = {p.name[len("part-"):-len(".parquet")]: p for p in root.glob(PART)}
    client = DataApiClient()
    total, reused, empty = 0, 0, []
    for row in tqdm(todo.itertuples(), total=len(todo), desc="Markets"):
        end = pd.Timestamp(row.end_ts_utc)
        # Fixed bounds (no now()) keep DiskCache keys stable across resumes.
        start_ts = int(pd.Timestamp(row.start_ts_utc).timestamp())
        end_ts = int(end.timestamp()) + 1  # the window is [start, end]
        if row.condition_id in have:
            if reuse(have[row.condition_id], start_ts, end_ts, row.yes_token_id):
                reused += 1
                continue
            have[row.condition_id].unlink()
        out = root / (f"contract_type={row.contract_type}/year={end.year}/month={end.month:02d}"
                      f"/part-{row.condition_id}.parquet")
        trades = []
        async for fill in client.iter_market_fills(row.condition_id, start_ts, end_ts):
            t = normalize_dataapi_fill(fill, market_id=row.condition_id, yes_token_id=row.yes_token_id)
            if t is not None:
                trades.append(t)
        trades = sort_trades(trades)
        if not trades:
            empty.append(row)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(pd.DataFrame([t.model_dump() for t in trades])), out)
        total += len(trades)
    log.info("pull loop done", new_trades=total, reused_files=reused, markets_without_trades=len(empty))
    root.mkdir(parents=True, exist_ok=True)
    cols = ["condition_id", "event_id", "company_id", "contract_type", "volume_shares", "start_ts_utc", "end_ts_utc"]
    pd.DataFrame([{c: getattr(r, c) for c in cols} for r in empty], columns=cols).to_csv(root / "_no_trades.csv", index=False)
    if empty:
        log.warning("markets with volume but 0 trades in their window", n=len(empty), report=str(root / "_no_trades.csv"))
    (root / "_SUCCESS").touch()


if __name__ == "__main__":
    asyncio.run(main())
