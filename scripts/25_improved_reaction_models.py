"""Script 25: literature-informed reaction model specs, compared against the
plain-OLS baselines from script 24 in one unified, pre-specified sweep.

Context (2026-10-14): script 24 found that no simple linear form (OLS,
through-origin OLS, Huber) generalizes out of sample for predicting
Polymarket's y_logit_24h from the real stock's bracketed log-return --
val/test r2 negative for all three. Before concluding there's nothing to
find, three research passes (event-study/price-discovery, prediction-market-
specific, pairs-trading/null-result literature) converged on a few concrete,
parsimonious extensions worth testing:

  - Winsorized regression (Leone, Minutti-Meza & Wasley 2012): outlier-driven
    instability is the single most common cause of an OLS slope flipping
    between train and test in archival finance regressions.
  - Volatility-standardized regressor (Bernard & Thomas 1989; Livnat &
    Mendenhall 2006, SUE methodology): raw log-return conflates firm-specific
    volatility scale with "surprise" -- standardizing by each company's own
    historical volatility should make the slope comparable across our
    heterogeneous cross-section of companies.
  - Price-level / boundary-compression interaction (Wolfers & Zitzewitz 2004;
    Snowberg & Wolfers 2010 favorite-longshot bias): a logit-space contract
    already near 0 or 1 is mechanically less sensitive to the same news than
    one near 50% (the logit link's derivative is p0*(1-p0)), so the same real
    stock move should produce a smaller Polymarket reaction near the
    boundaries -- this is a single interaction term motivated by a documented
    mechanism, not a free-form nonlinearity.

Every form is fit on TRAIN only, model selection happens on VAL only, and
TEST is touched exactly once for the winner -- same discipline as script 24.
Trying more forms raises the chance one looks good by luck alone, so the
permutation test's significance threshold is Bonferroni-corrected for the
total number of forms compared across script 24 and this script.

A real simplification, stated plainly: company volatility is computed once
from each company's full pulled price history (not a point-in-time trailing
window). It never touches the y_logit_24h target, so it is not label
leakage, but it is not strictly point-in-time either -- a finer trailing-
window version is a reasonable future refinement, not done here for
simplicity.

Reads: results/public_market_benchmark_rows.parquet (now includes
price_at_article), data/stocks/daily_prices.parquet.

Writes: results/improved_reaction_models.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor, LinearRegression

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
STOCKS_PATH = Path("data/stocks/daily_prices.parquet")
OUT_PATH = Path("results/improved_reaction_models.json")
N_PERMUTATIONS = 2000
RNG_SEED = 0
WINSOR_PCTILE = 1.0  # winsorize at 1st/99th percentile, thresholds from TRAIN only

log = get_logger(__name__)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    if ss_tot == 0:
        return None
    ss_res = np.sum((y_true - y_pred) ** 2)
    return float(1 - ss_res / ss_tot)


def _company_volatility(stocks_df: pd.DataFrame) -> dict[str, float]:
    """Std of each company's own daily log-return, from its full pulled price
    history. See module docstring for why this is a stated simplification."""
    out = {}
    for cid, grp in stocks_df.sort_values("date").groupby("company_id"):
        log_returns = np.log(grp["adj_close"].to_numpy()[1:] / grp["adj_close"].to_numpy()[:-1])
        out[str(cid)] = float(np.std(log_returns))
    return out


def _build_feature_sets(df: pd.DataFrame, company_vol: dict[str, float]) -> pd.DataFrame:
    out = df.copy()
    out["p0"] = _sigmoid(out["price_at_article"].to_numpy())
    out["boundary_compression"] = out["p0"] * (1 - out["p0"])
    out["company_vol"] = out["company_id"].map(company_vol)
    # A handful of companies may have too few price rows for a nonzero std;
    # guard against divide-by-zero rather than silently producing inf.
    out["company_vol"] = out["company_vol"].replace(0, np.nan)
    return out


def _fit_candidates(train: pd.DataFrame) -> dict:
    x = train["stock_log_return"].to_numpy()
    y = train["y_logit_24h"].to_numpy()

    candidates = {}

    candidates["ols_intercept"] = {
        "model": LinearRegression(fit_intercept=True).fit(x.reshape(-1, 1), y),
        "feature_fn": lambda d: d["stock_log_return"].to_numpy().reshape(-1, 1),
    }
    candidates["ols_through_origin"] = {
        "model": LinearRegression(fit_intercept=False).fit(x.reshape(-1, 1), y),
        "feature_fn": lambda d: d["stock_log_return"].to_numpy().reshape(-1, 1),
    }
    candidates["huber_intercept"] = {
        "model": HuberRegressor().fit(x.reshape(-1, 1), y),
        "feature_fn": lambda d: d["stock_log_return"].to_numpy().reshape(-1, 1),
    }

    # Winsorized through-origin: thresholds computed from TRAIN only, same
    # thresholds applied at predict time so val/test are never used to
    # decide the clipping bounds.
    lo, hi = np.percentile(x, [WINSOR_PCTILE, 100 - WINSOR_PCTILE])
    x_wins = np.clip(x, lo, hi)
    candidates["winsorized_through_origin"] = {
        "model": LinearRegression(fit_intercept=False).fit(x_wins.reshape(-1, 1), y),
        "feature_fn": lambda d: np.clip(d["stock_log_return"].to_numpy(), lo, hi).reshape(-1, 1),
        "winsor_bounds": (float(lo), float(hi)),
    }

    # Volatility-standardized through-origin (BMP/SUE-style surprise scaling).
    vol_ok = train["company_vol"].notna()
    x_vol = (train.loc[vol_ok, "stock_log_return"] / train.loc[vol_ok, "company_vol"]).to_numpy()
    y_vol = train.loc[vol_ok, "y_logit_24h"].to_numpy()
    candidates["vol_standardized_through_origin"] = {
        "model": LinearRegression(fit_intercept=False).fit(x_vol.reshape(-1, 1), y_vol),
        "feature_fn": lambda d: (d["stock_log_return"] / d["company_vol"]).to_numpy().reshape(-1, 1),
    }

    # Price-level / boundary-compression interaction: y ~ b1*x + b2*x*p0(1-p0),
    # no intercept (through origin, consistent with "no stock move -> no
    # reason to expect a Polymarket move").
    X_interact = np.column_stack([
        train["stock_log_return"].to_numpy(),
        (train["stock_log_return"] * train["boundary_compression"]).to_numpy(),
    ])
    candidates["price_level_interaction"] = {
        "model": LinearRegression(fit_intercept=False).fit(X_interact, y),
        "feature_fn": lambda d: np.column_stack([
            d["stock_log_return"].to_numpy(),
            (d["stock_log_return"] * d["boundary_compression"]).to_numpy(),
        ]),
    }

    return candidates


def _predict(candidate: dict, df: pd.DataFrame) -> np.ndarray:
    X = candidate["feature_fn"](df)
    return candidate["model"].predict(X)


def fit_reaction_models(df: pd.DataFrame) -> dict:
    train = df[df["split"] == "train"]
    val = df[df["split"] == "val"]
    test = df[df["split"] == "test"]

    candidates = _fit_candidates(train)

    val_r2 = {}
    for name, c in candidates.items():
        mask = val["company_vol"].notna() if name == "vol_standardized_through_origin" else pd.Series(True, index=val.index)
        sub = val[mask]
        pred = _predict(c, sub)
        val_r2[name] = _r2(sub["y_logit_24h"].to_numpy(), pred) or -np.inf

    best_r2 = max(val_r2.values())
    any_beats_baseline = best_r2 > 0
    near_best = [n for n, r2 in val_r2.items() if r2 >= best_r2 - 0.005]
    # Tie-break toward the simplest/most parsimonious form among near-ties.
    simplicity_order = [
        "ols_through_origin", "winsorized_through_origin", "vol_standardized_through_origin",
        "price_level_interaction", "ols_intercept", "huber_intercept",
    ]
    chosen_name = next((n for n in simplicity_order if n in near_best), near_best[0])
    chosen = candidates[chosen_name]

    test_mask = test["company_vol"].notna() if chosen_name == "vol_standardized_through_origin" else pd.Series(True, index=test.index)
    test_sub = test[test_mask]
    test_pred = _predict(chosen, test_sub)
    test_r2 = _r2(test_sub["y_logit_24h"].to_numpy(), test_pred)

    coef = chosen["model"].coef_.tolist()
    intercept = float(getattr(chosen["model"], "intercept_", 0.0))

    return {
        "n_train": len(train), "n_val": len(val), "n_test": len(test),
        "forms_compared": list(candidates.keys()),
        "n_forms_compared_this_script": len(candidates),
        "val_r2_by_candidate": val_r2,
        "any_candidate_beats_no_relationship_baseline_on_val": any_beats_baseline,
        "chosen_model": chosen_name,
        "chosen_model_coefficients": coef,
        "chosen_model_intercept": intercept,
        "held_out_test_r2": test_r2,
        "held_out_test_n": len(test_sub),
        "honest_conclusion": (
            "Still no candidate beats a flat baseline out of sample, even after adding "
            "literature-motivated extensions (winsorizing, volatility standardization, "
            "price-level/boundary-compression interaction). The weak pooled correlation "
            "does not appear to reflect a stable, generalizable functional relationship "
            "in any of the forms tested."
            if not any_beats_baseline else
            f"'{chosen_name}' beats the flat baseline on val; see held_out_test_r2 for "
            "its real, once-only test performance."
        ),
        "_chosen_candidate_obj": chosen,  # consumed by main(), not serialized
    }


def backtest_pair_trade(df: pd.DataFrame, candidate: dict, chosen_name: str, n_forms_total: int) -> dict:
    test = df[df["split"] == "test"].copy()
    if chosen_name == "vol_standardized_through_origin":
        test = test[test["company_vol"].notna()]

    predicted = _predict(candidate, test)
    actual = test["y_logit_24h"].to_numpy()

    nonzero = predicted != 0
    predicted, actual = predicted[nonzero], actual[nonzero]
    n = len(predicted)

    hit_rate = float((np.sign(predicted) == np.sign(actual)).mean())
    pnl_sign = np.sign(predicted) * actual
    pnl_mag = predicted * actual

    rng = np.random.default_rng(RNG_SEED)
    null_means = np.empty(N_PERMUTATIONS)
    for i in range(N_PERMUTATIONS):
        shuffled = rng.permutation(predicted)
        null_means[i] = np.mean(np.sign(shuffled) * actual)

    real_mean = pnl_sign.mean()
    percentile = float((null_means < real_mean).mean())
    raw_p_one_sided = max(1.0 - percentile, 1.0 / (N_PERMUTATIONS + 1))
    bonferroni_p = min(1.0, raw_p_one_sided * n_forms_total)

    return {
        "n_trades": n,
        "directional_hit_rate": hit_rate,
        "directional_hit_rate_baseline": 0.5,
        "mean_pnl_log_odds_sign_based": float(pnl_sign.mean()),
        "mean_pnl_log_odds_magnitude_weighted": float(pnl_mag.mean()),
        "permutation_test": {
            "n_permutations": N_PERMUTATIONS,
            "real_strategy_percentile_vs_null": percentile,
            "raw_one_sided_p": raw_p_one_sided,
            "n_forms_compared_total": n_forms_total,
            "bonferroni_corrected_p": bonferroni_p,
            "interpretation": (
                f"Bonferroni-corrected for {n_forms_total} total candidate forms compared "
                "across both scripts (per Harvey, Liu & Zhu 2016's point that the "
                "conventional significance bar is too lax once the number of specifications "
                "tried is accounted for). Significant at 0.05 only if bonferroni_corrected_p < 0.05."
            ),
        },
    }


def main() -> None:
    if not ROWS_PATH.exists():
        print(f"{ROWS_PATH} not found -- run scripts/23_benchmark_vs_public_market.py first.")
        return
    if not STOCKS_PATH.exists():
        print(f"{STOCKS_PATH} not found -- run scripts/22_pull_public_stock_prices.py first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    stocks_df = pd.read_parquet(STOCKS_PATH)
    company_vol = _company_volatility(stocks_df)
    df = _build_feature_sets(df, company_vol)

    log.info("improved_models_start", n_rows=len(df), n_companies_with_vol=len(company_vol))

    model_result = fit_reaction_models(df)
    chosen_candidate = model_result.pop("_chosen_candidate_obj")

    # Same discipline as script 24: when NO candidate actually beats the
    # baseline on val, "chosen_model" is just an arbitrary tie-break among
    # losers, not a validated winner -- backtesting it as-is risks exactly
    # the intercept sign-degeneracy artifact script 24 caught (intercept
    # dominates the predicted sign for typical small moves, regardless of
    # the real stock's direction). In that case, run the diagnostic backtest
    # on the through-origin form instead, whose predicted sign is always
    # just sign(stock_log_return) -- the same fallback script 24 used.
    backtest_name = model_result["chosen_model"]
    backtest_candidate = chosen_candidate
    if not model_result["any_candidate_beats_no_relationship_baseline_on_val"] and backtest_name != "ols_through_origin":
        backtest_name = "ols_through_origin"
        backtest_candidate = _fit_candidates(df[df["split"] == "train"])["ols_through_origin"]
        model_result["backtest_form_note"] = (
            "No candidate validated on val, so the backtest below uses ols_through_origin "
            "(clean, no-intercept sign) rather than the nominal tie-break winner "
            f"('{model_result['chosen_model']}'), to avoid an intercept-driven sign artifact."
        )

    # Total forms compared across script 24 (3) and this script (6, which
    # re-includes the same 3 baselines -- count each distinct form once).
    n_forms_total = len(set(model_result["forms_compared"]) | {"ols_intercept", "ols_through_origin", "huber_intercept"})
    backtest_result = backtest_pair_trade(df, backtest_candidate, backtest_name, n_forms_total)

    result = {"reaction_model": model_result, "pairs_trade_backtest": backtest_result}

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
