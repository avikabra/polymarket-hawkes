"""Script 16b: Cohort-stratified CV ablation — does the ladder correction help?

The original head-to-head ablation (scripts/16_train_linear_baseline.py
--target y_logit_24h vs y_logit_24h_ladder, using the production temporal
split) was uninformative: val (n=20) was entirely singleton cohorts, test's
cohorts averaged 347 members — a train/test cohort-size mismatch specific to
that temporal split, not a real test of the isotonic correction. See
src/analysis/ladder_cv_ablation.py's module docstring for the full reasoning
on why non-temporal CV is the right tool for this specific question (a
target-transformation comparison, not a forecasting evaluation) — same
precedent as scripts/09b_matching_ablation.py's all-pairs-no-split approach.

Uses ALL valid_24h rows for a category (ignores the production split column
entirely — this script does not touch or affect that split), 5-fold CV
stratified by ladder cohort size so every fold gets a representative mix of
singleton/small/large cohorts, fitting scripts/16's own LinearModel
(RidgeCV) out-of-fold for both y_logit_24h and y_logit_24h_ladder.

Usage:
    uv run python scripts/16b_ladder_cv_ablation.py --category price_ladder
    uv run python scripts/16b_ladder_cv_ablation.py --category all-ladder-categories

Reads:  data/analysis/shock_embeddings.parquet
Writes: results/ladder_cv_ablation.parquet (per-category summary)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.analysis.ladder_cv_ablation import stratified_cohort_folds
from src.evaluation.metrics import compute_r2_oos
from src.models.linear import LinearModel
from src.utils import get_logger

SHOCK_PATH = Path("data/analysis/shock_embeddings.parquet")
RESULTS_PATH = Path("results/ladder_cv_ablation.parquet")

# corporate_event is a singleton category by construction (no ladder — nothing
# to ablate). market_cap_ladder has 0 rows under the current split/date range.
# revenue_ladder/valuation_ladder are included when they clear MIN_ROWS.
_LADDER_CATEGORIES = ["price_ladder", "revenue_ladder", "valuation_ladder"]
MIN_ROWS = 50  # below this, 5-fold CV per stratum is too thin to trust

log = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cohort-stratified CV ablation for the ladder correction.")
    p.add_argument(
        "--category", default="all-ladder-categories",
        choices=_LADDER_CATEGORIES + ["all-ladder-categories"],
    )
    p.add_argument("--embedding", choices=["shock", "raw"], default="shock")
    p.add_argument("--n-splits", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def _run_cv(X: np.ndarray, y: np.ndarray, folds: np.ndarray, n_splits: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (out-of-fold predictions, held-out targets), aligned."""
    preds = np.empty_like(y)
    for fold_idx in range(n_splits):
        test_mask = folds == fold_idx
        train_mask = ~test_mask
        model = LinearModel()
        model.fit(X[train_mask], y[train_mask])
        preds[test_mask] = model.predict(X[test_mask])
    return preds, y


def _ablate_category(df: pd.DataFrame, category: str, emb_col: str, n_splits: int, seed: int) -> dict | None:
    sub = df[(df["category"] == category) & (df["valid_24h"] == True)].copy()  # noqa: E712
    if len(sub) < MIN_ROWS:
        print(f"{category}: only {len(sub)} valid_24h rows (< {MIN_ROWS}) — skipping, too thin to trust.")
        return None

    X = np.stack(sub[emb_col].tolist()).astype(np.float64)
    y_raw = sub["y_logit_24h"].to_numpy(dtype=np.float64)
    y_ladder = sub["y_logit_24h_ladder"].to_numpy(dtype=np.float64)
    cohort_sizes = sub["ladder_n_members_used_24h"]

    folds = stratified_cohort_folds(cohort_sizes, n_splits=n_splits, seed=seed)

    pred_raw, _ = _run_cv(X, y_raw, folds, n_splits)
    pred_ladder, _ = _run_cv(X, y_ladder, folds, n_splits)

    r2_raw = compute_r2_oos(y_raw, pred_raw)
    mse_raw = float(np.mean((y_raw - pred_raw) ** 2))
    r2_ladder = compute_r2_oos(y_ladder, pred_ladder)
    mse_ladder = float(np.mean((y_ladder - pred_ladder) ** 2))

    return {
        "category": category,
        "n_rows": len(sub),
        "n_singleton_cohorts": int((cohort_sizes == 1).sum()),
        "median_cohort_size": float(cohort_sizes.median()),
        "r2_oof_raw": r2_raw,
        "mse_oof_raw": mse_raw,
        "r2_oof_ladder": r2_ladder,
        "mse_oof_ladder": mse_ladder,
    }


def main() -> None:
    args = _parse_args()
    emb_col = "shock_embedding" if args.embedding == "shock" else "raw_embedding"

    if not SHOCK_PATH.exists():
        print("shock_embeddings.parquet not found — run script 13 first.")
        return

    df = pd.read_parquet(SHOCK_PATH)
    categories = (
        _LADDER_CATEGORIES if args.category == "all-ladder-categories" else [args.category]
    )

    results = []
    for cat in categories:
        row = _ablate_category(df, cat, emb_col, args.n_splits, args.seed)
        if row is not None:
            results.append(row)

    if not results:
        print("No category had enough rows to ablate.")
        return

    results_df = pd.DataFrame(results)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(results_df), RESULTS_PATH)

    print()
    print(f"{'category':20s} {'n_rows':>7s} {'n_single':>9s} {'med_cohort':>10s}  "
          f"{'R2_raw':>8s} {'R2_ladder':>10s}  {'MSE_raw':>8s} {'MSE_ladder':>11s}  verdict")
    print("-" * 110)
    for r in results:
        if r["r2_oof_ladder"] > r["r2_oof_raw"]:
            verdict = "ladder helps"
        elif r["r2_oof_ladder"] < r["r2_oof_raw"]:
            verdict = "ladder hurts"
        else:
            verdict = "no difference"
        print(
            f"{r['category']:20s} {r['n_rows']:7d} {r['n_singleton_cohorts']:9d} "
            f"{r['median_cohort_size']:10.1f}  {r['r2_oof_raw']:8.4f} {r['r2_oof_ladder']:10.4f}  "
            f"{r['mse_oof_raw']:8.4f} {r['mse_oof_ladder']:11.4f}  {verdict}"
        )
    print()
    print(f"Results written: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
