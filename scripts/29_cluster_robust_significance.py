"""Script 29: is the original pooled correlation itself trustworthy?

Context (2026-10-14): 12 different modeling approaches across scripts 24-28
(6 literature-motivated forms, a domain-specific match-quality moderator, a
tighter reaction window, a liquidity interaction, a cross-sectional company-
level check, and within-company fixed effects) have ALL failed to generalize
out of sample. That specific pattern -- a population-level correlation with
p~1e-35, but literally no functional form transferring from train to val/test
-- is a known symptom of non-independent observations inflating a standard
correlation test's apparent significance. Many rows here share the same
company and overlapping time windows (several articles about the same
company within days of each other share correlated stock-return and
Polymarket-reaction observations), which violates the i.i.d. assumption
behind the p-values already reported. This project has hit exactly this bug
before: the original parent_event_id bootstrap collapsed to one cluster
because of a different-but-related issue (see novel_math_design.md).

This script does not try another model. It re-examines whether the
ORIGINAL finding (signed/magnitude correlation between y_logit_24h and
stock_log_return, from results/public_market_benchmark.json) survives a
cluster-robust bootstrap, resampling by COMPANY (not by row) -- the standard
fix for clustered data (companies are the natural cluster unit here, since
within-company observations are not independent).

Reads: results/public_market_benchmark_rows.parquet

Writes: results/cluster_robust_significance.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
OUT_PATH = Path("results/cluster_robust_significance.json")
N_BOOTSTRAP = 5000
RNG_SEED = 0

log = get_logger(__name__)


def cluster_bootstrap_ci(df: pd.DataFrame, value_cols: tuple[str, str], cluster_col: str = "company_id") -> dict:
    """Block bootstrap: resample CLUSTERS (companies) with replacement, each
    time taking ALL of that company's rows, then recompute the statistic on
    the resampled pooled dataset. This correctly propagates within-cluster
    correlation into the CI's width, unlike a naive row-level bootstrap."""
    rng = np.random.default_rng(RNG_SEED)
    clusters = df[cluster_col].unique()
    n_clusters = len(clusters)
    cluster_groups = {c: df[df[cluster_col] == c] for c in clusters}

    def stat(d: pd.DataFrame) -> float:
        a = d[value_cols[0]].to_numpy()
        b = d[value_cols[1]].to_numpy()
        if len(d) < 10 or np.std(a) == 0 or np.std(b) == 0:
            return np.nan
        rho, _ = spearmanr(a, b)
        return rho

    point_estimate = stat(df)

    boot_stats = np.empty(N_BOOTSTRAP)
    for i in range(N_BOOTSTRAP):
        sampled_clusters = rng.choice(clusters, size=n_clusters, replace=True)
        resampled = pd.concat([cluster_groups[c] for c in sampled_clusters], ignore_index=True)
        boot_stats[i] = stat(resampled)

    boot_stats = boot_stats[~np.isnan(boot_stats)]
    ci_lo, ci_hi = np.percentile(boot_stats, [2.5, 97.5])
    frac_positive = float((boot_stats > 0).mean())

    return {
        "n_clusters": n_clusters,
        "n_bootstrap": len(boot_stats),
        "point_estimate_spearman_rho": float(point_estimate),
        "cluster_robust_95pct_ci": [float(ci_lo), float(ci_hi)],
        "ci_excludes_zero": bool(ci_lo > 0 or ci_hi < 0),
        "fraction_of_bootstrap_draws_positive": frac_positive,
        "interpretation": (
            "If the cluster-robust CI excludes zero, the original finding survives proper "
            "accounting for non-independent (same-company) observations -- the relationship "
            "is real but apparently too unstable in sign/magnitude across time to model, which "
            "is itself the honest conclusion. If the CI includes zero, the original p~1e-35 "
            "significance was likely inflated by treating correlated rows as independent, "
            "which would explain why NO functional form has generalized across 12 attempts: "
            "there may be nothing stable there to model in the first place."
        ),
    }


def main() -> None:
    if not ROWS_PATH.exists():
        print(f"{ROWS_PATH} not found -- run scripts/23_benchmark_vs_public_market.py first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    log.info("cluster_robust_start", n_rows=len(df), n_companies=df["company_id"].nunique())

    result = {
        "signed_correlation_cluster_robust": cluster_bootstrap_ci(
            df, ("y_logit_24h", "stock_log_return")
        ),
    }

    # Same check on the TEST split alone, since that's where every model's
    # generalization actually failed -- if the relationship doesn't even
    # cluster-bootstrap as significant within test, that specific failure is
    # unsurprising rather than mysterious.
    test_df = df[df["split"] == "test"]
    result["signed_correlation_cluster_robust_test_split_only"] = cluster_bootstrap_ci(
        test_df, ("y_logit_24h", "stock_log_return")
    )

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
