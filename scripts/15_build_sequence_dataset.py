"""Script 15: Validate ArticleSequenceDataset and print per-category/split statistics.

Reads: data/analysis/shock_embeddings.parquet
Prints: per-category/split observation counts, y_logit_6h mean/std, padding statistics
No output file written; diagnostic only.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.training.dataset import ArticleSequenceDataset, CAT_LABEL
from src.utils import get_logger

SHOCK_PATH = Path("data/analysis/shock_embeddings.parquet")

log = get_logger(__name__)

CONTRACT_COLS = [
    "article_id", "market_id", "shock_embedding", "raw_embedding",
    "category", "split", "canonical_ts", "parent_event_id",
    "y_logit_6h", "valid_6h", "news_type", "directional_impact",
]

CATEGORY_FILTERS: list[tuple[str, str | None]] = [
    ("all", None),
    ("sports-only", "sports"),
    ("politics-only", "politics"),
    ("geopolitics-only", "geopolitics"),
]


def _check_padding(dataset: ArticleSequenceDataset, n_samples: int = 5) -> dict:
    """Sample items and collect padding statistics."""
    n = min(n_samples, len(dataset))
    pad_counts: list[int] = []
    mask_shapes: list[tuple] = []
    for i in range(n):
        item = dataset[i]
        mask = item["mask"]
        mask_shapes.append(tuple(mask.shape))
        pad_counts.append(int((~mask).sum().item()))
    return {"pad_counts": pad_counts, "mask_shapes": mask_shapes}


def main() -> None:
    if not SHOCK_PATH.exists():
        print("shock_embeddings.parquet not found — run script 13 first.")
        return

    df = pd.read_parquet(SHOCK_PATH)
    print(f"\n=== Dataset overview ===")
    print(f"Total rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    missing = [c for c in CONTRACT_COLS if c not in df.columns]
    if missing:
        print(f"WARNING: missing contract columns: {missing}")
    else:
        print("Contract column check: PASSED")

    # Per-(category, split) y_logit_6h stats
    print("\n=== y_logit_6h mean/std per (category, split) ===")
    valid_df = df[df["valid_6h"] == True].copy()  # noqa: E712
    for cat in sorted(valid_df["category"].unique()):
        for split in ["train", "val", "test"]:
            sub = valid_df[(valid_df["category"] == cat) & (valid_df["split"] == split)]
            if len(sub) == 0:
                continue
            vals = sub["y_logit_6h"].dropna()
            print(
                f"  category={cat:12s} split={split:5s}  n={len(sub):5d}"
                f"  mean={vals.mean():.4f}  std={vals.std():.4f}"
            )

    # ArticleSequenceDataset instantiation and padding stats
    print("\n=== ArticleSequenceDataset per (filter, split) ===")
    parquet_path = str(SHOCK_PATH)
    K = 5

    for filter_label, cat_filter in CATEGORY_FILTERS:
        for split in ["train", "val", "test"]:
            try:
                ds = ArticleSequenceDataset(
                    parquet_path=parquet_path,
                    split=split,
                    K=K,
                    category_filter=cat_filter,
                )
            except Exception as exc:
                print(f"  [{filter_label}][{split}] ERROR: {exc}")
                continue

            n = len(ds)
            print(f"  [{filter_label:16s}][{split}]  len={n}")
            if n > 0:
                stats = _check_padding(ds, n_samples=5)
                print(f"    mask shapes: {stats['mask_shapes']}")
                print(f"    pad counts (zeros in mask): {stats['pad_counts']}")

    print("\nDone — no output written (diagnostic only).")


if __name__ == "__main__":
    main()
