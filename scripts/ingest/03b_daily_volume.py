"""Step 6: write data/polymarket/daily_volume.parquet from the pulled trades.

Columns: condition_id, day (ET), dollars, shares, cum_dollars (through that day). Also prints how
many contracts reach each liquidity floor of config/contracts.yaml, and checks each contract's
traded shares against Gamma's volumeNum (shares).

    uv run python scripts/ingest/03b_daily_volume.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import yaml

from src.ingest.daily_volume import build_daily_volume


def main() -> None:
    cfg = yaml.safe_load(open("config/contracts.yaml"))
    mk = pd.read_parquet(Path(cfg["paths"]["out_dir"]) / "markets.parquet")
    kept = mk[mk["excluded_reason"].isna()]
    dv = build_daily_volume(cfg["paths"]["trades"], kept)
    out = Path(cfg["paths"]["daily_volume"])
    out.parent.mkdir(parents=True, exist_ok=True)
    dv.to_parquet(out, index=False)
    tot = dv.groupby("condition_id")[["dollars", "shares"]].sum()
    print(f"{len(dv)} contract-days, {len(tot)} of {len(kept)} kept contracts traded -> {out}")
    for name, floor in cfg["liquidity"].items():
        print(f"{name}: {int((tot['dollars'] >= floor).sum())} contracts reach ${floor:,} by their end")
    v = kept.drop_duplicates("condition_id").set_index("condition_id")["volume_shares"].reindex(tot.index)
    print(f"traded shares vs Gamma volumeNum: {int(((tot['shares'] - v).abs() <= 0.01 * v.clip(lower=1)).sum())} "
          f"of {len(tot)} within 1%")


if __name__ == "__main__":
    main()
