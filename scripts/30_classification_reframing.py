"""Script 30: reframe as classification -- the breakthrough from script 29.

Context (2026-10-14): script 29's cluster-robust bootstrap found the SIGNED
correlation between y_logit_24h and stock_log_return is real even within the
test split alone (rho=0.198, 95% CI [0.049, 0.366], excludes zero) -- but
every regression-based model (scripts 24-28, 12 forms) still failed to
generalize as a magnitude-matching equation. The reconciling fact, found by
checking directly: P(y_logit_24h > 0) is only ~20% in every split (these
Polymarket contracts decay toward "no" ~80% of the time regardless of the
stock's move -- a real structural base rate, not noise). A through-origin
regression implicitly assumes E[y|x=0]=0, which is badly wrong given this
skew, and a raw 50%-coin-flip hit-rate baseline was the wrong yardstick for
the same reason (an "always predict negative" rule already gets ~80%).

The right framing given a real rank correlation riding on top of a skewed
base rate is classification, not magnitude regression: does knowing the
real stock's return shift the PROBABILITY that Polymarket's logit increases,
relative to its ~20% base rate? Evaluated with AUC (appropriate for
imbalanced classes and exactly the ranking-based question Spearman
correlation already answered "yes" to) rather than R2 or raw accuracy
against a 50% baseline.

Same discipline as every other script here: fit on train, select on val
(AUC > 0.5 is the baseline to beat), touch test once.

Reads: results/public_market_benchmark_rows.parquet

Writes: results/classification_reframing.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
OUT_PATH = Path("results/classification_reframing.json")
RNG_SEED = 0
N_PERMUTATIONS = 2000

log = get_logger(__name__)


def _auc_permutation_p(y_true: np.ndarray, y_score: np.ndarray, real_auc: float) -> dict:
    rng = np.random.default_rng(RNG_SEED)
    null_aucs = np.empty(N_PERMUTATIONS)
    for i in range(N_PERMUTATIONS):
        shuffled = rng.permutation(y_score)
        null_aucs[i] = roc_auc_score(y_true, shuffled)
    percentile = float((null_aucs < real_auc).mean())
    return {
        "null_mean_auc": float(null_aucs.mean()),
        "null_std_auc": float(null_aucs.std()),
        "real_auc_percentile_vs_null": percentile,
    }


def classification_model(df: pd.DataFrame) -> dict:
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    base_rate = {
        "train": float((train["y_logit_24h"] > 0).mean()),
        "val": float((val["y_logit_24h"] > 0).mean()),
        "test": float((test["y_logit_24h"] > 0).mean()),
    }

    x_train = train["stock_log_return"].to_numpy().reshape(-1, 1)
    y_train = (train["y_logit_24h"] > 0).astype(int).to_numpy()
    model = LogisticRegression().fit(x_train, y_train)

    x_val = val["stock_log_return"].to_numpy().reshape(-1, 1)
    y_val = (val["y_logit_24h"] > 0).astype(int).to_numpy()
    val_auc = roc_auc_score(y_val, model.predict_proba(x_val)[:, 1])
    beats_baseline = val_auc > 0.5

    result = {
        "base_rate_p_y_positive_by_split": base_rate,
        "coefficient_on_stock_log_return": float(model.coef_[0][0]),
        "intercept_logit": float(model.intercept_[0]),
        "val_auc": float(val_auc),
        "beats_baseline_auc_0.5_on_val": bool(beats_baseline),
    }

    if beats_baseline:
        x_test = test["stock_log_return"].to_numpy().reshape(-1, 1)
        y_test = (test["y_logit_24h"] > 0).astype(int).to_numpy()
        test_scores = model.predict_proba(x_test)[:, 1]
        test_auc = roc_auc_score(y_test, test_scores)
        result["held_out_test_auc"] = float(test_auc)
        result["held_out_test_permutation_test"] = _auc_permutation_p(y_test, test_scores, test_auc)
        result["conclusion"] = (
            "Beats the 0.5 AUC baseline on val; held_out_test_auc is the real, once-only "
            "generalization check, with a permutation test for significance."
        )
    else:
        result["conclusion"] = (
            "Does not beat the 0.5 AUC baseline on val -- the classification reframing "
            "does not generalize either, despite the robust rank correlation found in script 29."
        )

    return result


def main() -> None:
    if not ROWS_PATH.exists():
        print(f"{ROWS_PATH} not found -- run scripts/23_benchmark_vs_public_market.py first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    log.info("classification_reframing_start", n_rows=len(df))

    result = {"classification_model": classification_model(df)}

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
