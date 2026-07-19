"""Generate a synthetic shock_embeddings.parquet for pipeline smoke-testing.

The schema exactly mirrors the real output of scripts 12+13, so the full
W4-6 pipeline (scripts 15-21) can be exercised without the real W1-3 data.
Useful for:
  - Local smoke-testing after edits
  - Dry-run on Colab before uploading real data
  - CI regression checks

Usage:
    uv run python scripts/make_synthetic_shock_embeddings.py
    uv run python scripts/make_synthetic_shock_embeddings.py --out data/analysis/shock_embeddings.parquet --n 600 --seed 42
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

# Real embedding dimension (E5-large-v2)
EMBEDDING_DIM = 768

# Category distribution mirrors expected real data
_CATEGORIES = ["nfl", "nba", "politics", "geopolitics"]
_SPLITS = ["train", "val", "test"]
_NEWS_TYPES = ["quantitative", "qualitative", "high_attention", "ambiguous"]
_DIR_IMPACTS = [-1, 0, 1]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate synthetic shock_embeddings.parquet.")
    p.add_argument(
        "--out",
        default="data/analysis/shock_embeddings.parquet",
        help="Output path (default: data/analysis/shock_embeddings.parquet)",
    )
    p.add_argument(
        "--n",
        type=int,
        default=600,
        help="Total number of rows (default: 600; ≥300 recommended for meaningful splits)",
    )
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    rng = np.random.default_rng(args.seed)
    n = args.n

    # Assign splits: ~60% train, 20% val, 20% test
    split_labels = (
        ["train"] * int(n * 0.6)
        + ["val"] * int(n * 0.2)
        + ["test"] * (n - int(n * 0.6) - int(n * 0.2))
    )
    rng.shuffle(split_labels)

    # Assign categories with roughly equal shares
    cat_labels = (_CATEGORIES * (n // len(_CATEGORIES) + 1))[:n]
    rng.shuffle(cat_labels)

    # Assign markets: ~20 unique markets, each with several articles
    n_markets = max(20, n // 10)
    market_ids = [f"mkt_{i:04d}" for i in range(n_markets)]
    row_market_ids = [market_ids[i % n_markets] for i in range(n)]

    # Parent events: groups of ~3 markets
    parent_event_ids = [f"ev_{mid_id % (n_markets // 3):04d}" for mid_id in range(n_markets)]
    market_to_event = dict(zip(market_ids, parent_event_ids))

    # Base timestamp: spread over ~2 years of seconds (matches real data scale)
    base_ts = 1_680_000_000  # ~April 2023 UTC
    ts_range = 2 * 365 * 24 * 3600  # 2 years in seconds
    canonical_ts = sorted(rng.integers(base_ts, base_ts + ts_range, size=n).tolist())

    # Synthetic embeddings: unit-normal, float32, shape (n, EMBEDDING_DIM)
    shock_emb = rng.standard_normal((n, EMBEDDING_DIM)).astype(np.float32)
    raw_emb = rng.standard_normal((n, EMBEDDING_DIM)).astype(np.float32)

    # Reaction targets (log-odds changes, realistic std ~0.1–0.3)
    y_6h = rng.normal(0.0, 0.15, size=n).astype(np.float32)
    y_1h = y_6h * 0.5 + rng.normal(0.0, 0.05, size=n).astype(np.float32)
    y_24h = y_6h * 1.5 + rng.normal(0.0, 0.1, size=n).astype(np.float32)

    rows = []
    for i in range(n):
        mid = row_market_ids[i]
        rows.append({
            "article_id": f"art_{i:06d}",
            "market_id": mid,
            "category": cat_labels[i],
            "split": split_labels[i],
            "canonical_ts": int(canonical_ts[i]),
            "valid_6h": True,
            "valid_1h": bool(rng.random() > 0.1),
            "valid_24h": bool(rng.random() > 0.05),
            "y_logit_6h": float(y_6h[i]),
            "y_logit_1h": float(y_1h[i]),
            "y_logit_24h": float(y_24h[i]),
            "shock_embedding": shock_emb[i].tolist(),
            "raw_embedding": raw_emb[i].tolist(),
            "news_type": _NEWS_TYPES[i % len(_NEWS_TYPES)],
            "directional_impact": _DIR_IMPACTS[i % len(_DIR_IMPACTS)],
            "parent_event_id": market_to_event[mid],
            # lambda_chosen is optional metadata from purging; include for schema completeness
            "lambda_chosen": float(rng.uniform(0.01, 10.0)),
        })

    df = pd.DataFrame(rows)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print(f"Written {len(df)} rows → {out_path}")
    print(f"  Embedding dim:  {EMBEDDING_DIM}")
    print(f"  Split counts:   {df['split'].value_counts().to_dict()}")
    print(f"  Category counts:{df['category'].value_counts().to_dict()}")
    print(f"  y_logit_6h std: {df['y_logit_6h'].std():.4f}")
    print(f"\nRun 'uv run python scripts/15_build_sequence_dataset.py' to validate.")


if __name__ == "__main__":
    main()
