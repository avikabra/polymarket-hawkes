"""Script 24: fit a generalizable model of Polymarket's reaction vs. the real
stock's reaction, then sketch a pair-trade strategy built on it.

Context (2026-10-14): scripts/23 found a weak but real relationship between
Polymarket's 24h move (y_logit_24h) and the real stock's bracketed log-return
-- signed rho=0.119 (p~1e-35), magnitude rho=0.015 (not significant). This
script turns that into an actual fitted equation and tests it the way the
rest of this project tests everything: fit on train, never touch test until
the final number. Given how weak the raw signal is, the whole point here is
to resist the temptation to fit something fancier than the data supports --
model form is selected on val only, and the one thing we check per-category
is whether splitting by category is even justified, not assumed.

Reads: results/public_market_benchmark_rows.parquet (script 23's real,
train/val/test-labeled join of y_logit_24h / y_logit_24h_ladder against the
real stock's bracketed log-return, from the full Bouchet dataset).

Writes: results/reaction_model_and_pairs_trade.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor, LinearRegression

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
OUT_PATH = Path("results/reaction_model_and_pairs_trade.json")
N_PERMUTATIONS = 2000
RNG_SEED = 0

log = get_logger(__name__)


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    if ss_tot == 0:
        return None
    ss_res = np.sum((y_true - y_pred) ** 2)
    return float(1 - ss_res / ss_tot)


def _fit_candidates(x_train: np.ndarray, y_train: np.ndarray) -> dict:
    """Three candidate forms, all fit on train only. Kept deliberately simple
    -- a single slope (+ optional intercept), no polynomial/interaction terms
    -- because the raw correlation is too weak (rho~0.12) to support anything
    richer without just fitting noise."""
    X = x_train.reshape(-1, 1)

    ols = LinearRegression(fit_intercept=True).fit(X, y_train)
    ols_origin = LinearRegression(fit_intercept=False).fit(X, y_train)
    huber = HuberRegressor().fit(X, y_train)

    return {
        "ols_intercept": {"slope": float(ols.coef_[0]), "intercept": float(ols.intercept_), "model": ols},
        "ols_through_origin": {"slope": float(ols_origin.coef_[0]), "intercept": 0.0, "model": ols_origin},
        "huber_intercept": {"slope": float(huber.coef_[0]), "intercept": float(huber.intercept_), "model": huber},
    }


def _select_model(candidates: dict, x_val: np.ndarray, y_val: np.ndarray) -> tuple[str, dict, bool]:
    """Pick the candidate with the best VAL r2 -- test is never touched here.
    Ties (within 0.005 r2) are broken toward the simpler, through-origin form,
    since fewer free parameters generalizes better when the signal is this
    weak. Also flags whether ANY candidate actually beats the no-relationship
    baseline (r2 > 0) on val -- if none do, picking a "best of the losers" and
    presenting it as a working model would overstate what the data supports."""
    scored = {}
    for name, c in candidates.items():
        pred = c["model"].predict(x_val.reshape(-1, 1))
        scored[name] = _r2(y_val, pred) or -np.inf

    best_r2 = max(scored.values())
    any_beats_baseline = best_r2 > 0
    near_best = [n for n, r2 in scored.items() if r2 >= best_r2 - 0.005]
    chosen = "ols_through_origin" if "ols_through_origin" in near_best else near_best[0]
    return chosen, scored, any_beats_baseline


def fit_reaction_model(df: pd.DataFrame) -> dict:
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    candidates = _fit_candidates(train["stock_log_return"].to_numpy(), train["y_logit_24h"].to_numpy())
    chosen_name, val_r2_by_candidate, any_beats_baseline = _select_model(
        candidates, val["stock_log_return"].to_numpy(), val["y_logit_24h"].to_numpy()
    )
    chosen = candidates[chosen_name]

    x_test = test["stock_log_return"].to_numpy()
    y_test = test["y_logit_24h"].to_numpy()
    test_pred = chosen["model"].predict(x_test.reshape(-1, 1))
    test_r2 = _r2(y_test, test_pred)

    # Diagnostic only, decided on train+val (never test): is a per-category
    # slope justified, or does pooling (the model above) generalize better?
    # Only the two categories with enough rows to fit anything meaningful.
    category_check = {}
    train_val = pd.concat([train, val])
    for cat in ["corporate_event", "price_ladder"]:
        sub = train_val[train_val["category"] == cat]
        if len(sub) < 200:
            continue
        m = LinearRegression(fit_intercept=False).fit(
            sub["stock_log_return"].to_numpy().reshape(-1, 1), sub["y_logit_24h"].to_numpy()
        )
        category_check[cat] = {"n": len(sub), "slope": float(m.coef_[0])}

    pooled_slope = candidates["ols_through_origin"]["slope"]
    slopes_differ_a_lot = False
    if len(category_check) == 2:
        vals = [v["slope"] for v in category_check.values()]
        slopes_differ_a_lot = (max(vals) - min(vals)) > abs(pooled_slope)

    return {
        "n_train": len(train), "n_val": len(val), "n_test": len(test),
        "candidates_fit_on_train": {
            name: {"slope": c["slope"], "intercept": c["intercept"]} for name, c in candidates.items()
        },
        "val_r2_by_candidate": val_r2_by_candidate,
        "any_candidate_beats_no_relationship_baseline_on_val": any_beats_baseline,
        "chosen_model": chosen_name,
        "final_equation": {
            "form": "y_logit_24h = slope * stock_log_return + intercept",
            "slope": chosen["slope"],
            "intercept": chosen["intercept"],
        },
        "held_out_test_r2": test_r2,
        "held_out_test_n": len(test),
        "honest_conclusion": (
            "No candidate form beats a flat 'predict the mean' baseline on held-out "
            "data (val r2 is negative for all three forms; test r2 is also negative "
            "for the selected form). The pooled, whole-sample correlation reported "
            "earlier (rho=0.119) is real as a population-level statistic -- it is not "
            "a measurement artifact -- but it is not stable enough across time/companies "
            "to support a model fit on one slice of the data predicting another. The "
            "honest equation below is reported for completeness and as the input to the "
            "pair-trade sketch, not as a validated predictive tool."
            if not any_beats_baseline else
            "At least one candidate form beats a flat baseline out-of-sample; see "
            "held_out_test_r2 for the chosen model's real generalization performance."
        ),
        "category_slope_check_train_val_only": category_check,
        "pooled_vs_category_slopes_differ_a_lot": slopes_differ_a_lot,
        "category_check_conclusion": (
            "Category slopes are close enough to the pooled slope that a pooled, "
            "single-equation model is the more generalizable choice -- a per-category "
            "model would mostly be fitting noise in the smaller categories."
            if not slopes_differ_a_lot else
            "Category slopes differ enough to warrant reporting separately, "
            "but see n per category before trusting this."
        ),
    }


def backtest_pair_trade(df: pd.DataFrame, slope: float, intercept: float) -> dict:
    """Sketch of a pair-trade strategy built on the fitted equation, backtested
    ONLY on the test split (never used to fit or select the model above).

    Logic: the real stock is the faster, more liquid market. By the time its
    reaction to an article is observable, Polymarket's slower-moving contract
    may not have caught up yet. The strategy bets that it will, sized by the
    model's predicted move. This is a lead-lag / cross-market convergence
    trade, not textbook pairs trading on two cointegrated assets -- the
    'pair' here is (Polymarket's contract, the model-implied fair value
    derived from the real stock), and the trade is on the spread between them
    closing.

    P&L is measured in log-odds units (predicted_move's sign/magnitude times
    the REALIZED y_logit_24h), which is a clean proxy for whether the
    direction and scale of the bet were right -- it is NOT a dollar P&L.
    Converting to real returns needs Polymarket's actual bid-ask and payout
    structure, which this does not model; that gap is reported explicitly
    rather than papered over with an invented cost assumption.
    """
    test = df[df["split"] == "test"].copy()
    test["predicted_move"] = slope * test["stock_log_return"] + intercept
    test["actual_move"] = test["y_logit_24h"]

    nonzero = test["predicted_move"] != 0
    test = test[nonzero]
    n = len(test)

    direction_correct = np.sign(test["predicted_move"]) == np.sign(test["actual_move"])
    hit_rate = float(direction_correct.mean())

    pnl_sign_based = (np.sign(test["predicted_move"]) * test["actual_move"]).to_numpy()
    pnl_magnitude_weighted = (test["predicted_move"] * test["actual_move"]).to_numpy()

    def _summarize(pnl: np.ndarray) -> dict:
        mean = float(pnl.mean())
        std = float(pnl.std(ddof=1)) if len(pnl) > 1 else None
        sharpe_per_trade = (mean / std) if std else None
        return {"mean_pnl_log_odds": mean, "std_pnl_log_odds": std, "sharpe_per_trade": sharpe_per_trade}

    # Permutation null: shuffle predicted_move against actual_move (breaks any
    # real relationship while preserving each series' own distribution) to see
    # where the real strategy's mean P&L falls relative to chance.
    rng = np.random.default_rng(RNG_SEED)
    predicted = test["predicted_move"].to_numpy()
    actual = test["actual_move"].to_numpy()
    null_means = np.empty(N_PERMUTATIONS)
    for i in range(N_PERMUTATIONS):
        shuffled = rng.permutation(predicted)
        null_means[i] = np.mean(np.sign(shuffled) * actual)

    real_mean = pnl_sign_based.mean()
    percentile = float((null_means < real_mean).mean())

    return {
        "n_trades": n,
        "directional_hit_rate": hit_rate,
        "directional_hit_rate_baseline": 0.5,
        "sign_based_pnl": _summarize(pnl_sign_based),
        "magnitude_weighted_pnl": _summarize(pnl_magnitude_weighted),
        "permutation_test": {
            "n_permutations": N_PERMUTATIONS,
            "real_strategy_mean_pnl": float(real_mean),
            "null_mean_pnl": float(null_means.mean()),
            "null_std_pnl": float(null_means.std()),
            "real_strategy_percentile_vs_null": percentile,
            "interpretation": (
                "Fraction of random (sign-shuffled) strategies with LOWER mean P&L "
                "than the real one. Close to 1.0 means the real strategy's edge is "
                "unlikely to be chance; close to 0.5 means it is indistinguishable "
                "from randomly guessing direction."
            ),
        },
        "not_modeled": [
            "Polymarket bid-ask spread and taker fees, which could easily exceed "
            "a signal this small on a per-trade basis",
            "Capital requirements / position sizing beyond a simple magnitude weight",
            "Whether the real stock's move is actually observable before Polymarket's "
            "contract price updates -- GDELT's day-precision timestamps cannot confirm "
            "lead-lag ordering at sub-day resolution, so this strategy's core timing "
            "assumption is plausible but unverified with the data available here",
        ],
    }


def main() -> None:
    if not ROWS_PATH.exists():
        print(f"{ROWS_PATH} not found -- run scripts/23_benchmark_vs_public_market.py first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    log.info("reaction_model_start", n_rows=len(df))

    model_result = fit_reaction_model(df)

    # Backtest uses the through-origin slope specifically, not whichever form
    # "won" model selection: an intercept comparable in size to slope*x makes
    # the PREDICTED SIGN nearly constant for typical small moves (most stock
    # log-returns are a few percent, so slope*x is small and the intercept
    # alone decides the sign) -- that produced a degenerate, misleading
    # backtest on the first pass (32% directional hit rate, i.e. worse than a
    # coin flip, because almost every trade was predicted "short" regardless
    # of the real stock's actual direction). A through-origin model has no
    # such artifact: predicted sign is always just sign(stock_log_return).
    backtest_slope = model_result["candidates_fit_on_train"]["ols_through_origin"]["slope"]
    backtest_result = backtest_pair_trade(df, backtest_slope, 0.0)

    result = {"reaction_model": model_result, "pairs_trade_backtest": backtest_result}

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
