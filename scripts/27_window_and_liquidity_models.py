"""Script 27: two more ideas, neither from the literature search.

1. Tight stock-return window: close on the article's own day to the next
   close, instead of day-before to day-after. The event-study/price-discovery
   literature review flagged window misalignment between the two markets'
   reaction timescales as the most likely root cause of why nothing has
   generalized so far (scripts 24-26) -- this tests that directly by
   comparing the same model form on a tighter, better-aligned window.

2. Liquidity interaction: y_logit_24h ~ b1*x + b2*x*log1p(volume_24h_usdc).
   A thin, illiquid Polymarket contract shouldn't track real-world news the
   same way a liquid one does -- standard market-microstructure reasoning
   (liquid markets incorporate information faster/more completely), and
   something no outside literature about OUR specific matching pipeline
   could suggest, since it needs Polymarket's own trade data.

Same discipline as scripts 24-26: fit train, select val, touch test once.
Running Bonferroni count now includes all forms tried across scripts 24-27.

Reads: results/public_market_benchmark_rows.parquet (now includes
stock_log_return_tight, volume_24h_usdc).

Writes: results/window_and_liquidity_models.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
OUT_PATH = Path("results/window_and_liquidity_models.json")
N_PERMUTATIONS = 2000
RNG_SEED = 0
N_FORMS_PRIOR = 7  # 6 from scripts 24-25 + 1 interaction model from script 26

log = get_logger(__name__)


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    if ss_tot == 0:
        return None
    ss_res = np.sum((y_true - y_pred) ** 2)
    return float(1 - ss_res / ss_tot)


def _fit_through_origin(x: np.ndarray, y: np.ndarray) -> LinearRegression:
    return LinearRegression(fit_intercept=False).fit(x.reshape(-1, 1), y)


def tight_window_model(df: pd.DataFrame) -> dict:
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    m = _fit_through_origin(train["stock_log_return_tight"].to_numpy(), train["y_logit_24h"].to_numpy())
    val_r2 = _r2(val["y_logit_24h"].to_numpy(), m.predict(val["stock_log_return_tight"].to_numpy().reshape(-1, 1)))
    beats_baseline = (val_r2 or -np.inf) > 0

    test_r2 = None
    if beats_baseline:
        test_r2 = _r2(test["y_logit_24h"].to_numpy(), m.predict(test["stock_log_return_tight"].to_numpy().reshape(-1, 1)))

    # Side-by-side: does the tight window even correlate better with the
    # outcome than the loose one did, regardless of model fit (a simpler,
    # model-free check of the core "window misalignment" hypothesis)?
    from scipy.stats import spearmanr
    rho_loose, p_loose = spearmanr(train["y_logit_24h"].abs(), train["stock_log_return"].abs())
    rho_tight, p_tight = spearmanr(train["y_logit_24h"].abs(), train["stock_log_return_tight"].abs())

    return {
        "slope": float(m.coef_[0]),
        "val_r2": val_r2,
        "beats_baseline_on_val": beats_baseline,
        "held_out_test_r2": test_r2,
        "train_magnitude_correlation_loose_window": {"rho": float(rho_loose), "p": float(p_loose)},
        "train_magnitude_correlation_tight_window": {"rho": float(rho_tight), "p": float(p_tight)},
        "conclusion": (
            "Tight window beats baseline on val; held_out_test_r2 is its real, "
            "once-only generalization check."
            if beats_baseline else
            "Tight window does not beat a flat baseline on val either -- window "
            "misalignment does not appear to be the root cause."
        ),
    }


def liquidity_interaction_model(df: pd.DataFrame) -> dict:
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    def features(d: pd.DataFrame) -> np.ndarray:
        x = d["stock_log_return"].to_numpy()
        liq = np.log1p(d["volume_24h_usdc"].to_numpy())
        return np.column_stack([x, x * liq])

    model = LinearRegression(fit_intercept=False).fit(features(train), train["y_logit_24h"].to_numpy())
    val_r2 = _r2(val["y_logit_24h"].to_numpy(), model.predict(features(val)))
    beats_baseline = (val_r2 or -np.inf) > 0

    test_r2 = None
    if beats_baseline:
        test_r2 = _r2(test["y_logit_24h"].to_numpy(), model.predict(features(test)))

    return {
        "form": "y_logit_24h = b1*stock_log_return + b2*stock_log_return*log1p(volume_24h_usdc)",
        "coefficients": model.coef_.tolist(),
        "val_r2": val_r2,
        "beats_baseline_on_val": beats_baseline,
        "held_out_test_r2": test_r2,
        "conclusion": (
            "Liquidity interaction beats baseline on val; held_out_test_r2 is its real, "
            "once-only generalization check."
            if beats_baseline else
            "Liquidity interaction does not beat a flat baseline on val -- Polymarket's "
            "own liquidity does not explain the instability either."
        ),
    }


def combined_model(df: pd.DataFrame) -> dict:
    """If both individual ideas show even partial promise, try them together
    -- but ONLY as a single additional pre-specified form, not a search over
    combinations, to avoid compounding the multiple-testing problem."""
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    def features(d: pd.DataFrame) -> np.ndarray:
        x = d["stock_log_return_tight"].to_numpy()
        liq = np.log1p(d["volume_24h_usdc"].to_numpy())
        return np.column_stack([x, x * liq])

    model = LinearRegression(fit_intercept=False).fit(features(train), train["y_logit_24h"].to_numpy())
    val_r2 = _r2(val["y_logit_24h"].to_numpy(), model.predict(features(val)))
    beats_baseline = (val_r2 or -np.inf) > 0

    test_r2 = None
    if beats_baseline:
        test_r2 = _r2(test["y_logit_24h"].to_numpy(), model.predict(features(test)))

    return {
        "form": "y_logit_24h = b1*stock_log_return_tight + b2*stock_log_return_tight*log1p(volume_24h_usdc)",
        "coefficients": model.coef_.tolist(),
        "val_r2": val_r2,
        "beats_baseline_on_val": beats_baseline,
        "held_out_test_r2": test_r2,
    }


def main() -> None:
    if not ROWS_PATH.exists():
        print(f"{ROWS_PATH} not found -- run scripts/23_benchmark_vs_public_market.py first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    log.info("window_liquidity_start", n_rows=len(df))

    result = {
        "tight_window_model": tight_window_model(df),
        "liquidity_interaction_model": liquidity_interaction_model(df),
    }
    result["combined_tight_window_and_liquidity"] = combined_model(df)

    n_forms_total = N_FORMS_PRIOR + 3
    result["multiple_testing_note"] = (
        f"3 new forms tested here (tight window, liquidity interaction, combined), on top of "
        f"{N_FORMS_PRIOR} from scripts 24-26 -- running total {n_forms_total} forms compared. "
        "Any held_out_test_r2 reported above beating a flat baseline should be read against "
        "this count, per Harvey, Liu & Zhu (2016)."
    )

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
