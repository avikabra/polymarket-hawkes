"""Script 28: two ideas at a DIFFERENT level of analysis than scripts 24-27.

Every prior attempt (scripts 24-27, 10 model forms total) tried to predict
ONE article's Polymarket reaction from THAT SAME article's real stock
reaction -- event-level prediction. All failed to generalize. Two different
questions, neither answered yet:

1. Cross-sectional (between-company): do companies whose stocks are
   generally more news-sensitive also have Polymarket contracts that are
   generally more news-sensitive? This aggregates across all of a company's
   articles, which should cancel out event-level noise (mismatched article
   timing, matching uncertainty, idiosyncratic trading noise) if there's a
   stable company-level "sensitivity" trait underneath it -- the kind of
   signal that could be invisible article-by-article but real in aggregate.

2. Within-company (fixed effects): once each company's average reaction
   level is removed, does the REMAINING variation in stock reaction still
   predict the remaining variation in Polymarket reaction? This is standard
   panel-data practice (company fixed effects) for exactly the case where
   cross-company heterogeneity (some companies just react more than others,
   for reasons unrelated to any single article) could be swamping a real
   within-company relationship in a pooled regression.

Reads: results/public_market_benchmark_rows.parquet

Writes: results/cross_sectional_and_fixed_effects.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import LinearRegression

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
OUT_PATH = Path("results/cross_sectional_and_fixed_effects.json")
RNG_SEED = 0
N_PERMUTATIONS = 2000

log = get_logger(__name__)


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    if ss_tot == 0:
        return None
    ss_res = np.sum((y_true - y_pred) ** 2)
    return float(1 - ss_res / ss_tot)


def cross_sectional_analysis(df: pd.DataFrame) -> dict:
    """Company-level: average |y_logit_24h| vs average |stock_log_return|,
    across all articles for that company, pooled across all splits (this is
    a between-company structural question, not an event-forecasting one, so
    it is not meant to generalize to NEW articles the way the event-level
    models were -- it is its own, separately-stated hypothesis)."""
    agg = df.groupby("company_id").agg(
        n=("y_logit_24h", "size"),
        mean_abs_poly=("y_logit_24h", lambda s: s.abs().mean()),
        mean_abs_stock=("stock_log_return", lambda s: s.abs().mean()),
    ).reset_index()
    agg = agg[agg["n"] >= 20]  # drop companies with too few articles for a stable average

    if len(agg) < 10:
        return {"status": "too_few_companies", "n_companies": len(agg)}

    rho, p_s = spearmanr(agg["mean_abs_poly"], agg["mean_abs_stock"])
    r, p_p = pearsonr(agg["mean_abs_poly"], agg["mean_abs_stock"])

    return {
        "status": "ok",
        "n_companies": len(agg),
        "min_articles_per_company_required": 20,
        "spearman_rho": float(rho), "spearman_p": float(p_s),
        "pearson_r": float(r), "pearson_p": float(p_p),
        "interpretation": (
            "Tests whether companies with generally larger real stock reactions to news "
            "also have generally larger Polymarket reactions, aggregating away event-level "
            "noise. A positive, significant correlation here would be a genuinely new, "
            "different claim from anything tested in scripts 24-27 (which all failed at "
            "the event level)."
        ),
    }


def fixed_effects_analysis(df: pd.DataFrame) -> dict:
    """Demean both y and x by each company's TRAIN-period mean (computed from
    train only, applied to val/test -- no leakage), then fit a through-origin
    slope on the demeaned train data and evaluate out-of-sample, same
    discipline as every other script in this series."""
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    company_mean_y = train.groupby("company_id")["y_logit_24h"].mean()
    company_mean_x = train.groupby("company_id")["stock_log_return"].mean()

    def demean(d: pd.DataFrame) -> pd.DataFrame:
        out = d.copy()
        out["y_demeaned"] = out["y_logit_24h"] - out["company_id"].map(company_mean_y)
        out["x_demeaned"] = out["stock_log_return"] - out["company_id"].map(company_mean_x)
        return out.dropna(subset=["y_demeaned", "x_demeaned"])

    train_d, val_d, test_d = demean(train), demean(val), demean(test)

    model = LinearRegression(fit_intercept=False).fit(
        train_d["x_demeaned"].to_numpy().reshape(-1, 1), train_d["y_demeaned"].to_numpy()
    )
    val_r2 = _r2(val_d["y_demeaned"].to_numpy(), model.predict(val_d["x_demeaned"].to_numpy().reshape(-1, 1)))
    beats_baseline = (val_r2 or -np.inf) > 0

    test_r2 = None
    if beats_baseline:
        test_r2 = _r2(test_d["y_demeaned"].to_numpy(), model.predict(test_d["x_demeaned"].to_numpy().reshape(-1, 1)))

    return {
        "n_train": len(train_d), "n_val": len(val_d), "n_test": len(test_d),
        "slope": float(model.coef_[0]),
        "val_r2": val_r2,
        "beats_baseline_on_val": beats_baseline,
        "held_out_test_r2": test_r2,
        "conclusion": (
            "Within-company variation beats baseline on val; held_out_test_r2 is its real, "
            "once-only generalization check -- this would mean company-level heterogeneity "
            "WAS masking a real relationship in the pooled regressions."
            if beats_baseline else
            "Within-company variation does not beat a flat baseline on val either -- "
            "cross-company heterogeneity does not appear to be masking a hidden relationship."
        ),
    }


def main() -> None:
    if not ROWS_PATH.exists():
        print(f"{ROWS_PATH} not found -- run scripts/23_benchmark_vs_public_market.py first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    log.info("cross_sectional_fe_start", n_rows=len(df), n_companies=df["company_id"].nunique())

    result = {
        "cross_sectional_company_level": cross_sectional_analysis(df),
        "within_company_fixed_effects": fixed_effects_analysis(df),
    }

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
