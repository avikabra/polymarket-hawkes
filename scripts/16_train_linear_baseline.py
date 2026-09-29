"""Script 16: Train linear (ridge) baseline.

Usage:
    uv run python scripts/16_train_linear_baseline.py --category all --embedding shock
    uv run python scripts/16_train_linear_baseline.py --category sports --embedding raw
    uv run python scripts/16_train_linear_baseline.py --target y_logit_24h_ladder

Reads:  data/analysis/shock_embeddings.parquet
Writes: models/checkpoints/linear_{category}_{embedding}.pkl
        results/metrics_all.parquet  (appended or created)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.evaluation.metrics import compute_r2_oos, compute_direction_accuracy
from src.models.linear import LinearModel
from src.utils import get_logger

SHOCK_PATH = Path("data/analysis/shock_embeddings.parquet")
CHECKPOINTS_DIR = Path("models/checkpoints")
RESULTS_PATH = Path("results/metrics_all.parquet")
LINEAR_TEST_PREDS_PATH = Path("results/linear_test_predictions.parquet")

SPORTS_CATS = {"nfl", "nba"}

log = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train linear ridge baseline.")
    p.add_argument(
        "--category",
        choices=["sports", "politics", "geopolitics", "all"],
        default="all",
    )
    p.add_argument(
        "--embedding",
        choices=["shock", "raw"],
        default="shock",
    )
    p.add_argument(
        "--target",
        choices=[
            "y_logit_1h", "y_logit_6h", "y_logit_24h",
            "y_logit_1h_ladder", "y_logit_6h_ladder", "y_logit_24h_ladder",
        ],
        default="y_logit_24h",
        help="Reaction-window column to predict. Defaults to y_logit_24h — the only "
        "window with meaningful coverage in this corpus (1h/6h are near-100%% null; "
        "see novel_math_design.md Fix 1). A _ladder target shares its validity column "
        "with the underlying window (e.g. y_logit_24h_ladder uses valid_24h).",
    )
    return p.parse_args()


def _valid_col_for_target(target: str) -> str:
    """Map a y_logit_{delta}h[_ladder] target to its valid_{delta}h column.

    A _ladder column has no separate validity flag of its own — it is only
    meaningful where the underlying valid_{delta}h was already True (see
    ladder_reaction.compute_ladder_adjusted_reactions).
    """
    window = target.removeprefix("y_logit_").removesuffix("_ladder")
    return f"valid_{window}"


def _filter_category(df: pd.DataFrame, category: str) -> pd.DataFrame:
    if category == "sports":
        return df[df["category"].isin(SPORTS_CATS)].copy()
    elif category in ("politics", "geopolitics"):
        return df[df["category"] == category].copy()
    return df.copy()


def _get_split(df: pd.DataFrame, split: str, category: str, emb_col: str, target_col: str):
    sub = df[df["split"] == split].copy()
    sub = _filter_category(sub, category)
    X = np.stack(sub[emb_col].tolist()).astype(np.float64)
    y = sub[target_col].to_numpy(dtype=np.float64)
    return X, y, sub


def main() -> None:
    args = _parse_args()
    emb_col = "shock_embedding" if args.embedding == "shock" else "raw_embedding"
    valid_col = _valid_col_for_target(args.target)

    if not SHOCK_PATH.exists():
        print("shock_embeddings.parquet not found — run script 13 first.")
        return

    df = pd.read_parquet(SHOCK_PATH)
    df = df[df[valid_col] == True].copy()  # noqa: E712

    log.info(
        "linear_baseline",
        category=args.category,
        embedding=args.embedding,
        target=args.target,
        n_rows=len(df),
    )

    X_train, y_train, _ = _get_split(df, "train", args.category, emb_col, args.target)
    X_val, y_val, _ = _get_split(df, "val", args.category, emb_col, args.target)
    X_test, y_test, test_sub = _get_split(df, "test", args.category, emb_col, args.target)

    if len(X_train) == 0:
        print(f"No training data for category={args.category}. Exiting.")
        return

    model = LinearModel()
    model.fit(X_train, y_train)

    val_pred = model.predict(X_val)
    val_mse = float(np.mean((y_val - val_pred) ** 2))
    print(f"Val MSE:        {val_mse:.6f}")
    print(f"Chosen lambda:  {model.alpha_:.4f}")

    test_pred = model.predict(X_test)
    test_r2 = compute_r2_oos(y_test, test_pred)
    test_dir_acc = compute_direction_accuracy(y_test, test_pred)
    print(f"Test R²_OOS:    {test_r2:.6f}")
    print(f"Test Dir Acc:   {test_dir_acc:.4f}")

    ckpt_name = f"linear_{args.category}_{args.embedding}.pkl"
    ckpt_path = CHECKPOINTS_DIR / ckpt_name
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    model.save(ckpt_path)
    print(f"Model saved:    {ckpt_path}")

    # Write per-row test predictions for H3 (shock + pooled run only — this is the
    # authoritative linear baseline for news_type decomposition per §5.2).
    if args.embedding == "shock" and args.category == "all":
        preds_df = pd.DataFrame({
            "y_true": y_test,
            "y_pred": test_pred,
            "news_type": test_sub["news_type"].fillna("").astype(str).values,
            "directional_impact": test_sub["directional_impact"].astype(int).values,
            "article_id": test_sub["article_id"].astype(str).values,
            "parent_event_id": test_sub["parent_event_id"].fillna("").astype(str).values,
        })
        LINEAR_TEST_PREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        preds_df.to_parquet(LINEAR_TEST_PREDS_PATH, index=False)
        print(f"Linear test predictions: {LINEAR_TEST_PREDS_PATH}")

    # Append to results/metrics_all.parquet
    row = {
        "arch": "linear",
        "category": args.category,
        "embedding": args.embedding,
        "target": args.target,
        "val_mse": val_mse,
        "lambda_chosen": model.alpha_,
        "test_r2_oos": test_r2,
        "test_direction_accuracy": test_dir_acc,
        "checkpoint": str(ckpt_path),
    }
    new_df = pd.DataFrame([row])
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if RESULTS_PATH.exists():
        existing = pd.read_parquet(RESULTS_PATH)
        if "target" not in existing.columns:
            # Pre-existing rows predate the --target flag; they were all
            # produced against the old hardcoded y_logit_6h column.
            existing["target"] = "y_logit_6h"
        # Remove any existing row for same arch/category/embedding/target
        mask = ~(
            (existing["arch"] == "linear")
            & (existing["category"] == args.category)
            & (existing["embedding"] == args.embedding)
            & (existing["target"] == args.target)
        )
        existing = existing[mask]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_parquet(RESULTS_PATH, index=False)
    print(f"Results written: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
