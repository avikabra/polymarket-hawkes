"""Script 31: a digital-option-style structural model (user's idea, 2026-10-14).

Context: 14 prior model forms (scripts 24-30) have all tried to predict
Polymarket's y_logit_24h from the real stock's return alone -- a pure
reduced-form relationship, with no reference to what the contract is
actually betting on. These price_ladder contracts are literally digital/
binary options ("will STOCK close above/below STRIKE by RESOLUTION_DATE"),
so classic digital-option pricing theory gives a specific, falsifiable
structural prediction instead of a generic correlation:

  P(S_T > K) ~= Phi(d2),  d2 = sign * ln(S_t / K) / (sigma * sqrt(T - t))

(sign = +1 for "above" contracts, -1 for "below", so d2 > 0 always means
"moving toward the outcome the contract is betting on"; sigma is the
stock's own historical volatility; T-t is time to resolution in years.)
Two structural, theory-motivated consequences, neither tried before:

  1. The REACTION to a given stock move should be bigger when LESS time is
     left to resolution (less time for the market to revert) -- i.e. the
     right regressor is the stock's move divided by sqrt(time remaining),
     not the raw move.
  2. The REACTION should be biggest when the stock is already near the
     strike ("at the money", maximum option gamma) and smallest when it is
     deep in/out of the money -- i.e. an interaction with phi(d2), the
     standard normal density at the PRE-EVENT moneyness level.

Scoped to price_ladder ONLY: strike_price is a per-share stock price for
this category (units match the real stock price), but is market cap /
revenue / something else for the other ladder categories -- ln(S/K) would
be comparing incompatible units there. Also filters out rows with
non-positive time_to_resolution_days (a real data artifact -- article
matched after the market had already resolved) and implausible strike
prices (>$100k or <=0, a small number of rows that are clearly a different
unit mistakenly tagged price_ladder, not real per-share prices).

Same discipline as scripts 24-30: fit train, select val, touch test once.

Reads: results/public_market_benchmark_rows.parquet, data/stocks/daily_prices.parquet.

Writes: results/digital_option_structural_model.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LinearRegression

from src.utils import get_logger

ROWS_PATH = Path("results/public_market_benchmark_rows.parquet")
STOCKS_PATH = Path("data/stocks/daily_prices.parquet")
OUT_PATH = Path("results/digital_option_structural_model.json")
MAX_PLAUSIBLE_STRIKE = 100_000.0

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


def _stock_price_at_or_before(company_dates: pd.DataFrame, article_date: pd.Timestamp) -> float | None:
    dates = company_dates["date"]
    idx = dates.searchsorted(article_date, side="right") - 1
    if idx < 0:
        return None
    return float(company_dates["adj_close"].iloc[idx])


def build_features(df: pd.DataFrame, stock_lookup: dict, company_vol: dict) -> pd.DataFrame:
    out = df[df["category"] == "price_ladder"].copy()
    out = out[(out["time_to_resolution_days"] > 0) &
              (out["strike_price"] > 0) & (out["strike_price"] <= MAX_PLAUSIBLE_STRIKE)]
    out = out[out["strike_direction"].isin(["above", "below"])]

    s_pre = []
    for _, row in out.iterrows():
        prices = stock_lookup.get(str(row["company_id"]))
        s_pre.append(_stock_price_at_or_before(prices, row["canonical_ts"]) if prices is not None else None)
    out["s_pre"] = s_pre
    out = out.dropna(subset=["s_pre"])
    out = out[out["s_pre"] > 0]

    out["company_vol"] = out["company_id"].map(company_vol).replace(0, np.nan)
    out = out.dropna(subset=["company_vol"])

    sign = np.where(out["strike_direction"] == "above", 1.0, -1.0)
    out["sign_adj"] = sign
    out["d2_raw"] = sign * np.log(out["s_pre"].to_numpy() / out["strike_price"].to_numpy())
    t_years = out["time_to_resolution_days"].to_numpy() / 365.0
    out["sqrt_t_years"] = np.sqrt(t_years)
    out["d2_std"] = out["d2_raw"] / (out["company_vol"].to_numpy() * out["sqrt_t_years"].to_numpy())
    out["phi_d2"] = norm.pdf(out["d2_std"].to_numpy())

    # Delta-d2 implied by the real stock's move over the reaction window,
    # same vol/time standardization as the pre-event level above.
    out["delta_d2_std"] = (out["sign_adj"] * out["stock_log_return"]) / (
        out["company_vol"].to_numpy() * out["sqrt_t_years"].to_numpy()
    )
    out["direction_adjusted_return"] = out["sign_adj"] * out["stock_log_return"]

    return out


def fit_and_select(train_x: np.ndarray, train_y: np.ndarray, val_x: np.ndarray, val_y: np.ndarray) -> dict:
    m = LinearRegression(fit_intercept=False).fit(train_x.reshape(-1, 1), train_y)
    val_r2 = _r2(val_y, m.predict(val_x.reshape(-1, 1)))
    return {"model": m, "slope": float(m.coef_[0]), "val_r2": val_r2}


def main() -> None:
    if not ROWS_PATH.exists() or not STOCKS_PATH.exists():
        print("Missing required inputs -- run scripts/22 and /23 first.")
        return

    df = pd.read_parquet(ROWS_PATH)
    stocks_df = pd.read_parquet(STOCKS_PATH)
    company_vol = _company_volatility(stocks_df)
    stock_lookup = {}
    for cid, grp in stocks_df.sort_values("date").groupby("company_id"):
        g = grp[["date", "adj_close"]].copy()
        g["date"] = pd.to_datetime(g["date"])
        stock_lookup[str(cid)] = g.reset_index(drop=True)

    feat = build_features(df, stock_lookup, company_vol)
    log.info("digital_option_model_start", n_rows=len(feat))

    train = feat[feat["split"] == "train"]
    val = feat[feat["split"] == "val"]
    test = feat[feat["split"] == "test"]

    candidates = {
        "direction_adjusted_return_only": ("direction_adjusted_return", "direction_adjusted_return"),
        "vol_time_standardized_shock": ("delta_d2_std", "delta_d2_std"),
        "gamma_weighted_raw_return": (None, None),  # built separately below (2-term interaction, not single col)
        "full_combined_shock_x_gamma": (None, None),
    }

    results = {
        "n_train": len(train), "n_val": len(val), "n_test": len(test),
        "candidates": {},
    }

    # Single-regressor forms.
    for name, (col, _) in [
        ("direction_adjusted_return_only", ("direction_adjusted_return", None)),
        ("vol_time_standardized_shock", ("delta_d2_std", None)),
    ]:
        fit = fit_and_select(
            train[col].to_numpy(), train["y_logit_24h"].to_numpy(),
            val[col].to_numpy(), val["y_logit_24h"].to_numpy(),
        )
        results["candidates"][name] = {"slope": fit["slope"], "val_r2": fit["val_r2"]}

    # Gamma-weighted raw return: y ~ b * (direction_adjusted_return * phi_d2_pre)
    for name, base_col in [
        ("gamma_weighted_raw_return", "direction_adjusted_return"),
        ("full_combined_shock_x_gamma", "delta_d2_std"),
    ]:
        x_train = (train[base_col] * train["phi_d2"]).to_numpy()
        x_val = (val[base_col] * val["phi_d2"]).to_numpy()
        fit = fit_and_select(x_train, train["y_logit_24h"].to_numpy(), x_val, val["y_logit_24h"].to_numpy())
        results["candidates"][name] = {"slope": fit["slope"], "val_r2": fit["val_r2"]}

    best_name = max(results["candidates"], key=lambda n: results["candidates"][n]["val_r2"] or -np.inf)
    best_r2 = results["candidates"][best_name]["val_r2"]
    beats_baseline = (best_r2 or -np.inf) > 0
    results["best_candidate_on_val"] = best_name
    results["beats_baseline_on_val"] = bool(beats_baseline)

    if beats_baseline:
        col_map = {
            "direction_adjusted_return_only": train["direction_adjusted_return"],
            "vol_time_standardized_shock": train["delta_d2_std"],
            "gamma_weighted_raw_return": train["direction_adjusted_return"] * train["phi_d2"],
            "full_combined_shock_x_gamma": train["delta_d2_std"] * train["phi_d2"],
        }
        test_col_map = {
            "direction_adjusted_return_only": test["direction_adjusted_return"],
            "vol_time_standardized_shock": test["delta_d2_std"],
            "gamma_weighted_raw_return": test["direction_adjusted_return"] * test["phi_d2"],
            "full_combined_shock_x_gamma": test["delta_d2_std"] * test["phi_d2"],
        }
        m = LinearRegression(fit_intercept=False).fit(
            col_map[best_name].to_numpy().reshape(-1, 1), train["y_logit_24h"].to_numpy()
        )
        test_pred = m.predict(test_col_map[best_name].to_numpy().reshape(-1, 1))
        results["held_out_test_r2"] = _r2(test["y_logit_24h"].to_numpy(), test_pred)
        results["conclusion"] = (
            f"'{best_name}' beats baseline on val; held_out_test_r2 is its real, "
            "once-only generalization check."
        )
    else:
        results["conclusion"] = (
            "None of the digital-option-structural forms beat a flat baseline on val. "
            "Strike price and time-to-resolution do not explain the instability either."
        )

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(json.dumps(results, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
