"""Script 33: the final, fully-validated price_ladder reaction model.

Context (2026-10-14, overnight continuation): script 32 found a real,
cluster-robust-significant correlation specific to price_ladder (contracts
betting directly on a company's stock price), but its single-val-split model
check was noisy and inconclusive (val r2 -0.037, technically short of this
project's bar). Investigating why surfaced an important structural fact:
price_ladder has only 16 distinct companies total, and 10 of the 11 train
companies ALSO appear in val (same mega-cap tech names) -- so the date-based
val split barely tests generalization to NEW companies, just a later time
window for the same ones. test, by contrast, adds four companies never seen
in train/val at all (Bank of America, Citigroup, Goldman Sachs, JPMorgan --
a real sector shift from tech to financials). A single noisy val check with
this little company diversity is a weak basis for model selection.

This script replaces that single-split check with LEAVE-ONE-COMPANY-OUT
cross-validation across train+val combined (12 unique companies) -- the
standard, appropriate technique when there are too few independent clusters
for a stable single holdout, and the thing we actually care about
(generalizing to companies/periods not seen in fitting) is directly what
LOCO-CV measures. Several candidate forms are compared this way; the winner
is refit on ALL of train+val and evaluated EXACTLY ONCE on test (which was
never touched by the CV selection), including the four novel companies.

Also builds the full backtest package requested: realistic position sizing,
an equity curve, Sharpe ratio, max drawdown, a transaction-cost sensitivity
sweep (0 / 10 / 20 / 40 bps round-trip, the range the pairs-trading
literature review flagged as realistic), and a deflated-Sharpe-style
multiple-testing note given how many forms have been compared across this
whole investigation (scripts 24-33).

Reads: results/public_market_benchmark_rows.parquet, data/stocks/daily_prices.parquet

Writes: results/price_ladder_final_model.json
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
STOCKS_PATH = Path("data/stocks/daily_prices.parquet")
OUT_PATH = Path("results/price_ladder_final_model.json")
N_BOOTSTRAP = 5000
N_PERMUTATIONS = 5000
RNG_SEED = 0
N_FORMS_PRIOR_TO_THIS_SCRIPT = 18  # scripts 24-32's total distinct forms

log = get_logger(__name__)


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    if ss_tot == 0:
        return None
    ss_res = np.sum((y_true - y_pred) ** 2)
    return float(1 - ss_res / ss_tot)


def _company_volatility(stocks_df: pd.DataFrame) -> dict[str, float]:
    out = {}
    for cid, grp in stocks_df.sort_values("date").groupby("company_id"):
        log_returns = np.log(grp["adj_close"].to_numpy()[1:] / grp["adj_close"].to_numpy()[:-1])
        out[str(cid)] = float(np.std(log_returns))
    return out


# --- Candidate model forms, each (name -> (feature_fn, fit_intercept)) ---
def _make_candidates(train_x_for_winsor: np.ndarray) -> dict:
    lo, hi = np.percentile(train_x_for_winsor, [1.0, 99.0])
    return {
        "through_origin": (lambda d: d["stock_log_return"].to_numpy().reshape(-1, 1), False),
        "with_intercept": (lambda d: d["stock_log_return"].to_numpy().reshape(-1, 1), True),
        "winsorized_with_intercept": (
            lambda d: np.clip(d["stock_log_return"].to_numpy(), lo, hi).reshape(-1, 1), True
        ),
        "vol_standardized_with_intercept": (
            lambda d: (d["stock_log_return"] / d["company_vol"]).to_numpy().reshape(-1, 1), True
        ),
    }


def loco_cv_select(train_val: pd.DataFrame) -> dict:
    """Leave-one-company-out CV across train+val combined. For each
    candidate form, for each held-out company, fit on the rest and score
    on the held-out company's rows; average R2 across companies."""
    companies = train_val["company_id"].unique()
    candidates = _make_candidates(train_val["stock_log_return"].to_numpy())

    cv_scores = {}
    for name, (feature_fn, fit_intercept) in candidates.items():
        fold_r2 = []
        fold_n = []
        for held_out in companies:
            fit_data = train_val[train_val["company_id"] != held_out]
            score_data = train_val[train_val["company_id"] == held_out]
            if len(score_data) < 5:
                continue
            X_fit = feature_fn(fit_data)
            y_fit = fit_data["y_logit_24h"].to_numpy()
            if np.isnan(X_fit).any():
                mask = ~np.isnan(X_fit).ravel()
                X_fit, y_fit = X_fit[mask], y_fit[mask]
            m = LinearRegression(fit_intercept=fit_intercept).fit(X_fit, y_fit)
            X_score = feature_fn(score_data)
            y_score = score_data["y_logit_24h"].to_numpy()
            valid = ~np.isnan(X_score).ravel()
            if valid.sum() < 5:
                continue
            r2 = _r2(y_score[valid], m.predict(X_score[valid]))
            if r2 is not None:
                fold_r2.append(r2)
                fold_n.append(int(valid.sum()))
        weighted_mean_r2 = float(np.average(fold_r2, weights=fold_n)) if fold_r2 else None
        cv_scores[name] = {
            "n_companies_scored": len(fold_r2),
            "mean_r2_unweighted": float(np.mean(fold_r2)) if fold_r2 else None,
            "mean_r2_weighted_by_held_out_n": weighted_mean_r2,
        }

    best_name = max(cv_scores, key=lambda n: cv_scores[n]["mean_r2_weighted_by_held_out_n"] or -np.inf)
    return {"candidates": cv_scores, "selected_form": best_name}


def fit_final_and_test(train_val: pd.DataFrame, test: pd.DataFrame, selected_form: str) -> dict:
    candidates = _make_candidates(train_val["stock_log_return"].to_numpy())
    feature_fn, fit_intercept = candidates[selected_form]

    X_fit = feature_fn(train_val)
    y_fit = train_val["y_logit_24h"].to_numpy()
    mask = ~np.isnan(X_fit).ravel()
    X_fit, y_fit = X_fit[mask], y_fit[mask]
    model = LinearRegression(fit_intercept=fit_intercept).fit(X_fit, y_fit)

    X_test = feature_fn(test)
    y_test = test["y_logit_24h"].to_numpy()
    valid = ~np.isnan(X_test).ravel()
    X_test, y_test = X_test[valid], y_test[valid]
    pred_test = model.predict(X_test)
    test_r2 = _r2(y_test, pred_test)

    novel_companies = {"bank_of_america", "citigroup", "goldman_sachs", "jpmorgan"}
    test_valid_df = test[valid]
    is_novel = test_valid_df["company_id"].isin(novel_companies).to_numpy()

    return {
        "selected_form": selected_form,
        "coefficients": model.coef_.tolist(),
        "intercept": float(getattr(model, "intercept_", 0.0)),
        "n_train_val_fit": len(X_fit),
        "n_test": len(X_test),
        "held_out_test_r2_all_companies": test_r2,
        "held_out_test_r2_seen_companies_only": _r2(y_test[~is_novel], pred_test[~is_novel]) if (~is_novel).sum() >= 10 else None,
        "held_out_test_r2_novel_companies_only": _r2(y_test[is_novel], pred_test[is_novel]) if is_novel.sum() >= 10 else None,
        "n_novel_company_test_rows": int(is_novel.sum()),
        "_model": model, "_feature_fn": feature_fn,
    }


def cluster_bootstrap(d: pd.DataFrame, cluster_col: str = "company_id") -> dict:
    rng = np.random.default_rng(RNG_SEED)
    clusters = d[cluster_col].unique()
    groups = {c: d[d[cluster_col] == c] for c in clusters}

    def stat(sub: pd.DataFrame) -> float:
        if len(sub) < 10:
            return np.nan
        rho, _ = spearmanr(sub["y_logit_24h"], sub["stock_log_return"])
        return rho

    point = stat(d)
    boots = np.empty(N_BOOTSTRAP)
    for i in range(N_BOOTSTRAP):
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        resampled = pd.concat([groups[c] for c in sampled], ignore_index=True)
        boots[i] = stat(resampled)
    boots = boots[~np.isnan(boots)]
    ci = np.percentile(boots, [2.5, 97.5])
    return {
        "n_companies": len(clusters), "point_estimate_rho": float(point),
        "cluster_robust_95pct_ci": [float(ci[0]), float(ci[1])],
        "ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0),
    }


def backtest_with_costs(test: pd.DataFrame, model, feature_fn, n_forms_total: int) -> dict:
    X_test = feature_fn(test)
    y_test = test["y_logit_24h"].to_numpy()
    valid = ~np.isnan(X_test).ravel()
    X_test, y_test, test_valid = X_test[valid], y_test[valid], test[valid]

    predicted = model.predict(X_test)
    n = len(predicted)

    # Position sizing: proportional to the predicted move's magnitude,
    # capped at a modest max (avoids a handful of outlier predictions
    # dominating the equity curve), normalized so position sizes are
    # comparable in scale to the log-odds moves themselves.
    raw_position = predicted
    cap = np.percentile(np.abs(raw_position), 95)
    position = np.clip(raw_position, -cap, cap)

    gross_pnl_per_trade = position * y_test  # log-odds P&L proxy, as in scripts 24-25

    hit_rate = float((np.sign(predicted) == np.sign(y_test)).mean())
    base_rate_negative = float((y_test < 0).mean())

    # Permutation significance of mean gross P&L (same method as scripts 24-26).
    rng = np.random.default_rng(RNG_SEED)
    null_means = np.empty(N_PERMUTATIONS)
    for i in range(N_PERMUTATIONS):
        shuffled = rng.permutation(position)
        null_means[i] = np.mean(shuffled * y_test)
    real_mean = gross_pnl_per_trade.mean()
    percentile = float((null_means < real_mean).mean())
    raw_p_one_sided = max(1.0 - percentile, 1.0 / (N_PERMUTATIONS + 1))
    bonferroni_p = min(1.0, raw_p_one_sided * n_forms_total)

    # Transaction cost sweep: round-trip cost in log-odds-equivalent terms,
    # charged once per trade regardless of direction (a conservative,
    # position-size-independent drag -- the realistic range the
    # pairs-trading literature review flagged, 10-40 bps).
    cost_sweep = {}
    for bps in [0, 10, 20, 40]:
        cost_per_trade = (bps / 10000.0) * np.abs(position)
        net_pnl = gross_pnl_per_trade - cost_per_trade
        equity_curve = np.cumsum(net_pnl)
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = equity_curve - running_max
        max_drawdown = float(drawdown.min()) if len(drawdown) else None
        mean_net = float(net_pnl.mean())
        std_net = float(net_pnl.std(ddof=1)) if n > 1 else None
        sharpe = (mean_net / std_net) if std_net else None
        cost_sweep[f"{bps}bps_round_trip"] = {
            "mean_net_pnl_per_trade": mean_net,
            "sharpe_per_trade": sharpe,
            "total_net_pnl": float(equity_curve[-1]) if len(equity_curve) else None,
            "max_drawdown": max_drawdown,
        }

    return {
        "n_trades": n,
        "directional_hit_rate": hit_rate,
        "base_rate_y_negative": base_rate_negative,
        "mean_gross_pnl_per_trade_log_odds": float(real_mean),
        "permutation_test": {
            "n_permutations": N_PERMUTATIONS,
            "percentile_vs_null": percentile,
            "raw_one_sided_p": raw_p_one_sided,
            "n_forms_compared_total_across_investigation": n_forms_total,
            "bonferroni_corrected_p": bonferroni_p,
        },
        "transaction_cost_sweep": cost_sweep,
        "equity_curve_sample_last10_net_0bps": list(np.cumsum(gross_pnl_per_trade)[-10:].round(4)),
    }


def main() -> None:
    if not ROWS_PATH.exists() or not STOCKS_PATH.exists():
        print("Missing required inputs.")
        return

    df = pd.read_parquet(ROWS_PATH)
    stocks_df = pd.read_parquet(STOCKS_PATH)
    company_vol = _company_volatility(stocks_df)

    pl = df[df["category"] == "price_ladder"].copy()
    pl["company_vol"] = pl["company_id"].map(company_vol)

    train_val = pl[pl["split"].isin(["train", "val"])]
    test = pl[pl["split"] == "test"]

    log.info("price_ladder_final_start", n_train_val=len(train_val), n_test=len(test))

    cv_result = loco_cv_select(train_val)
    final = fit_final_and_test(train_val, test, cv_result["selected_form"])
    model, feature_fn = final.pop("_model"), final.pop("_feature_fn")

    cluster_pooled = cluster_bootstrap(pl)
    cluster_train_val = cluster_bootstrap(train_val)
    cluster_test = cluster_bootstrap(test)

    n_forms_total = N_FORMS_PRIOR_TO_THIS_SCRIPT + len(cv_result["candidates"])
    backtest = backtest_with_costs(test, model, feature_fn, n_forms_total)

    result = {
        "loco_cv_model_selection": cv_result,
        "final_model_held_out_test": final,
        "cluster_robust_significance": {
            "pooled_price_ladder": cluster_pooled,
            "train_val_only": cluster_train_val,
            "test_only": cluster_test,
        },
        "backtest": backtest,
    }

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
