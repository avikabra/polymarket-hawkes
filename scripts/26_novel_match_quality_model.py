"""Script 26: a genuinely new model spec -- match-quality-moderated reaction.

Context (2026-10-14): six literature-motivated model forms (scripts 24-25)
all failed to generalize out of sample. The common thread: every form pools
ALL article-contract pairs together and fits one relationship. But Thread 1
(novel_math_design.md) already measured something no outside literature has
access to -- a per-pair match-quality score (embedding_score: pure text
similarity between the article and the contract, no volume component, so no
risk of the volume-tautology issue that weakened joint_score's external
validity in results/public_market_benchmark.json's Part B). The hypothesis
this script tests: the pooled relationship is unstable because it mixes
high-confidence matches (where the article plausibly drove both reactions)
with low-confidence ones (where the "match" may be coincidental, carrying no
real relationship at all) -- and that mixture's composition shifts across
train/val/test, which would explain exactly the sign/magnitude instability
already seen six times.

Two things are tested, both pre-specified before looking at test data:

1. A formal pooled interaction model: y_logit_24h ~ b1*x + b2*x*quality,
   fit train / selected val / tested once -- compared against the 6 existing
   forms under the running Bonferroni correction (now 7 forms total).

2. The more direct, more interpretable claim: split rows into
   low/mid/high embedding_score tiers using THRESHOLDS COMPUTED FROM TRAIN
   ONLY (no leakage), then compare the TEST-split magnitude correlation
   (|y_logit_24h| vs |stock_log_return|) within the high tier against the
   low tier. This needs no fitted slope -- it is a direct, held-out
   comparison of association strength by match quality. Significance is
   assessed with ONE pre-specified permutation test (shuffle tier labels
   within the test split, 2000 reps) on the single contrast
   Delta = rho_high - rho_low, which is the one hypothesis this script set
   out to test -- not a family of post-hoc comparisons.

Reads: results/public_market_benchmark_rows.parquet (now includes
embedding_score, joint_score).

Writes: results/novel_match_quality_model.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
PRIOR_RESULTS_PATH = Path("results/improved_reaction_models.json")
OUT_PATH = Path("results/novel_match_quality_model.json")
N_PERMUTATIONS = 2000
RNG_SEED = 0

log = get_logger(__name__)


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    if ss_tot == 0:
        return None
    ss_res = np.sum((y_true - y_pred) ** 2)
    return float(1 - ss_res / ss_tot)


def fit_interaction_model(df: pd.DataFrame) -> dict:
    """y_logit_24h ~ b1*stock_log_return + b2*stock_log_return*quality_centered.
    quality_centered uses the TRAIN mean of embedding_score for centering --
    the same constant is applied to val/test, so no leakage."""
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    train_mean_quality = train["embedding_score"].mean()

    def features(d: pd.DataFrame) -> np.ndarray:
        centered = d["embedding_score"].to_numpy() - train_mean_quality
        x = d["stock_log_return"].to_numpy()
        return np.column_stack([x, x * centered])

    model = LinearRegression(fit_intercept=False).fit(features(train), train["y_logit_24h"].to_numpy())
    val_r2 = _r2(val["y_logit_24h"].to_numpy(), model.predict(features(val)))

    # Load the prior 6 forms' val r2 for an honest side-by-side comparison.
    prior_val_r2 = {}
    if PRIOR_RESULTS_PATH.exists():
        with open(PRIOR_RESULTS_PATH) as f:
            prior_val_r2 = json.load(f)["reaction_model"]["val_r2_by_candidate"]

    best_prior = max(prior_val_r2.values()) if prior_val_r2 else -np.inf
    beats_prior = (val_r2 or -np.inf) > best_prior and (val_r2 or -np.inf) > 0

    test_r2 = None
    if beats_prior:
        test_r2 = _r2(test["y_logit_24h"].to_numpy(), model.predict(features(test)))

    return {
        "form": "y_logit_24h = b1*stock_log_return + b2*stock_log_return*(embedding_score - train_mean)",
        "coefficients": model.coef_.tolist(),
        "train_mean_quality_used_for_centering": float(train_mean_quality),
        "val_r2": val_r2,
        "prior_6_forms_best_val_r2": best_prior,
        "beats_prior_forms_and_baseline": beats_prior,
        "held_out_test_r2": test_r2,
        "conclusion": (
            "Interaction model beats both the baseline and the best of the 6 prior forms "
            "on val; held_out_test_r2 is its real, once-only generalization check."
            if beats_prior else
            "Interaction model does not beat the best prior form (or a flat baseline) on "
            "val, so test was not touched for this formal pooled model. The tier-split "
            "analysis below tests the same underlying hypothesis a different, more direct way."
        ),
    }


def tier_split_analysis(df: pd.DataFrame) -> dict:
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]

    lo_thresh, hi_thresh = np.percentile(train["embedding_score"], [33.333, 66.667])

    def assign_tier(scores: pd.Series) -> pd.Series:
        return pd.cut(scores, bins=[-np.inf, lo_thresh, hi_thresh, np.inf], labels=["low", "mid", "high"])

    test = test.copy()
    test["tier"] = assign_tier(test["embedding_score"])

    def tier_corr(d: pd.DataFrame) -> dict:
        if len(d) < 10:
            return {"n": len(d), "spearman_rho": None, "degenerate": True}
        rho, p = spearmanr(d["y_logit_24h"].abs(), d["stock_log_return"].abs())
        return {"n": len(d), "spearman_rho": float(rho), "spearman_p": float(p), "degenerate": False}

    by_tier = {tier: tier_corr(test[test["tier"] == tier]) for tier in ["low", "mid", "high"]}

    rho_high = by_tier["high"]["spearman_rho"] or 0.0
    rho_low = by_tier["low"]["spearman_rho"] or 0.0
    real_delta = rho_high - rho_low

    # ONE pre-specified permutation test on this single contrast: shuffle
    # which test rows are labeled high/low/mid (preserving each tier's real
    # count), recompute Delta = rho_high - rho_low each time.
    rng = np.random.default_rng(RNG_SEED)
    tier_labels = test["tier"].to_numpy()
    abs_y = test["y_logit_24h"].abs().to_numpy()
    abs_x = test["stock_log_return"].abs().to_numpy()
    null_deltas = np.empty(N_PERMUTATIONS)
    for i in range(N_PERMUTATIONS):
        shuffled = rng.permutation(tier_labels)
        high_mask = shuffled == "high"
        low_mask = shuffled == "low"
        rho_h = spearmanr(abs_y[high_mask], abs_x[high_mask])[0] if high_mask.sum() >= 10 else 0.0
        rho_l = spearmanr(abs_y[low_mask], abs_x[low_mask])[0] if low_mask.sum() >= 10 else 0.0
        null_deltas[i] = (rho_h or 0.0) - (rho_l or 0.0)

    percentile = float((null_deltas < real_delta).mean())

    # Supporting (not the primary claim): train-fit/test-eval R2 within each
    # tier, same through-origin discipline as scripts 24-25.
    out_of_sample_by_tier = {}
    for tier in ["low", "mid", "high"]:
        train_tier = train[assign_tier(train["embedding_score"]) == tier]
        test_tier = test[test["tier"] == tier]
        if len(train_tier) < 10 or len(test_tier) < 10:
            out_of_sample_by_tier[tier] = {"n_train": len(train_tier), "n_test": len(test_tier), "r2": None}
            continue
        x_train = train_tier["stock_log_return"].to_numpy().reshape(-1, 1)
        y_train = train_tier["y_logit_24h"].to_numpy()
        m = LinearRegression(fit_intercept=False).fit(x_train, y_train)
        pred_test = m.predict(test_tier["stock_log_return"].to_numpy().reshape(-1, 1))
        r2 = _r2(test_tier["y_logit_24h"].to_numpy(), pred_test)
        out_of_sample_by_tier[tier] = {
            "n_train": len(train_tier), "n_test": len(test_tier),
            "slope": float(m.coef_[0]), "r2": r2,
        }

    return {
        "tier_thresholds_from_train": {"low_max": float(lo_thresh), "high_min": float(hi_thresh)},
        "test_split_magnitude_correlation_by_tier": by_tier,
        "real_delta_high_minus_low": float(real_delta),
        "permutation_test": {
            "n_permutations": N_PERMUTATIONS,
            "null_mean_delta": float(null_deltas.mean()),
            "null_std_delta": float(null_deltas.std()),
            "real_delta_percentile_vs_null": percentile,
            "interpretation": (
                "Fraction of random tier-relabelings with a SMALLER high-minus-low "
                "correlation gap than the real one. Close to 1.0 means high-confidence "
                "matches show a reliably stronger real-stock relationship than "
                "low-confidence matches, not explainable by chance tier assignment."
            ),
        },
        "supporting_out_of_sample_r2_by_tier": out_of_sample_by_tier,
    }


def main() -> None:
    if not ROWS_PATH.exists():
        print(f"{ROWS_PATH} not found -- run scripts/23_benchmark_vs_public_market.py first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    log.info("novel_model_start", n_rows=len(df))

    result = {
        "interaction_model": fit_interaction_model(df),
        "tier_split_analysis": tier_split_analysis(df),
    }

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
