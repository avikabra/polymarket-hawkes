"""Script 13: Per-category ridge purging regression → shock embeddings.

Reads:
  data/analysis/tuples.parquet           (market chars + reaction windows)
  data/news/analysis_embeddings/          (float32 analysis embeddings)
  config/analysis.yaml                    (lambda grid, CV folds, splits)

Writes:
  data/analysis/shock_embeddings.parquet  (article_id, shock_embedding, lambda_chosen, category, split)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.analysis.purging import purge_by_category
from src.utils import get_logger

TUPLES_PATH = Path("data/analysis/tuples.parquet")
ANALYSIS_EMB_PATH = Path("data/news/analysis_embeddings/analysis_embeddings.parquet")
SHOCK_PATH = Path("data/analysis/shock_embeddings.parquet")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")

log = get_logger(__name__)


def _load_config() -> dict:
    cfg_path = Path("config/analysis.yaml")
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f)
    return {}


def main() -> None:
    if not TUPLES_PATH.exists():
        print("tuples.parquet not found — run script 12 first.")
        return
    if not ANALYSIS_EMB_PATH.exists():
        print("analysis_embeddings.parquet not found — run script 11 first.")
        return

    cfg = _load_config()
    purging_cfg = cfg.get("purging", {})
    splits_cfg = cfg.get("splits", {})

    lambda_grid = purging_cfg.get("lambda_grid", [0.1, 1.0, 10.0, 100.0])
    cv_folds = int(purging_cfg.get("cv_folds", 5))
    train_before = splits_cfg.get("train_before", "2025-01-01")
    val_before = (splits_cfg.get("val_range") or ["2025-01-01", "2025-07-01"])[1]

    tuples_df = pd.read_parquet(TUPLES_PATH)
    emb_df = pd.read_parquet(ANALYSIS_EMB_PATH)

    # Decode embedding bytes → numpy arrays
    if "embedding" in emb_df.columns and emb_df["embedding"].dtype == object:
        # Detect embedding dim from first row
        first = emb_df["embedding"].iloc[0]
        if isinstance(first, (bytes, bytearray)):
            emb_dim = len(first) // 4  # float32 = 4 bytes
            emb_df["analysis_embedding"] = emb_df["embedding"].apply(
                lambda b: np.frombuffer(b, dtype=np.float32)
            )
        else:
            emb_df["analysis_embedding"] = emb_df["embedding"]
    elif "analysis_embedding" not in emb_df.columns:
        print("Cannot find embedding column in analysis_embeddings.parquet")
        return

    # Join market resolution date from universe
    universe_df = pd.read_parquet(UNIVERSE_PATH)
    market_info = universe_df[["market_id", "resolved_at"]].copy()
    market_info["market_id"] = market_info["market_id"].astype(str)
    tuples_df["market_id"] = tuples_df["market_id"].astype(str)
    tuples_df = tuples_df.merge(market_info, on="market_id", how="left")

    log.info("purging", articles=len(tuples_df), categories=tuples_df["category"].unique().tolist())

    result_df = purge_by_category(
        tuples_df=tuples_df,
        embeddings_df=emb_df[["article_id", "analysis_embedding"]],
        train_before=train_before,
        val_before=val_before,
        lambda_grid=lambda_grid,
        cv_folds=cv_folds,
    )

    SHOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(result_df), SHOCK_PATH)

    for split in ["train", "val", "test"]:
        n = (result_df["split"] == split).sum()
        print(f"split={split}: {n} shock embeddings")
    print(f"Written: {SHOCK_PATH}")


if __name__ == "__main__":
    main()
