"""Script 23: benchmark Polymarket's reaction against the real public stock's reaction.

Context (2026-10-14): every prior result in this project compares Polymarket
against itself -- the matching score vs. Polymarket's own realized price move
(novel_math_design.md Thread 1); the prediction models and the ladder
correction vs. Polymarket's own target (Thread 2, scripts 16-21). None of it
checks whether the real, publicly-traded company also reacted, or whether
Polymarket's reaction is proportionate to the real market's. This script adds
that external benchmark, using scripts/22_pull_public_stock_prices.py's real
daily closes, and re-evaluates both novel-math threads against it, not just
the Polymarket-internal validation they already have.

Real stock reaction, defined honestly: GDELT gives day precision only, so we
cannot pin down intraday timing on either side. We bracket generously --
prior trading-day close to the first trading-day close at least one full day
after the article -- rather than claim false precision. This is a looser
window than Polymarket's own crisp 24h, not an exact apples-to-apples match;
a correlation found despite that looseness is if anything an understatement.

Reads:
  data/stocks/daily_prices.parquet         (script 22's real closes)
  data/analysis/shock_embeddings.parquet   (Polymarket's own y_logit_24h / y_logit_24h_ladder)
  data/analysis/tuples.parquet             (article_id -> canonical_ts, market_id)
  data/analysis/matching_ablation.parquet  (script 09b's real per-pair matching scores)
  data/polymarket/universe.parquet         (market_id -> company_id)
  data/polymarket/contract_groups.parquet  (group_id -> company_name)

Writes: results/public_market_benchmark.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr

from src.utils import get_logger

STOCKS_PATH = Path("data/stocks/daily_prices.parquet")
SHOCK_PATH = Path("data/analysis/shock_embeddings.parquet")
TUPLES_PATH = Path("data/analysis/tuples.parquet")
MATCHING_ABLATION_PATH = Path("data/analysis/matching_ablation.parquet")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
CONTRACT_GROUPS_PATH = Path("data/polymarket/contract_groups.parquet")
OUT_PATH = Path("results/public_market_benchmark.json")

log = get_logger(__name__)


def _build_stock_lookup(stocks_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """company_id -> its own daily_prices rows, sorted by date, date as datetime64."""
    out = {}
    for cid, grp in stocks_df.groupby("company_id"):
        g = grp[["date", "adj_close"]].copy()
        g["date"] = pd.to_datetime(g["date"])
        g = g.sort_values("date").reset_index(drop=True)
        out[str(cid)] = g
    return out


def _bracket_log_return(
    company_dates: pd.DataFrame, article_date: pd.Timestamp
) -> float | None:
    """Real stock log-return bracketing an article's calendar day.

    prior = last close strictly before article_date.
    next_ = first close at or after article_date + 1 day.
    Returns ln(next_/prior), or None if either side is missing (e.g. article
    near the edge of our pulled date range, or a market holiday gap too wide).
    """
    dates = company_dates["date"]
    closes = company_dates["adj_close"]

    prior_idx = dates.searchsorted(article_date, side="left") - 1
    if prior_idx < 0:
        return None
    next_cutoff = article_date + pd.Timedelta(days=1)
    next_idx = dates.searchsorted(next_cutoff, side="left")
    if next_idx >= len(dates):
        return None

    prior_close = closes.iloc[prior_idx]
    next_close = closes.iloc[next_idx]
    if prior_close <= 0 or next_close <= 0:
        return None
    return float(np.log(next_close / prior_close))


def _material_move_table(poly: np.ndarray, stock: np.ndarray, quantile: float = 0.75) -> dict:
    """2x2 contingency: did the stock move materially (top quantile of |stock|)
    vs. did Polymarket move materially (top quantile of |poly|), using each
    series' OWN distribution so the two very different units (log-odds vs.
    log-return) don't need an arbitrary shared cutoff."""
    poly_thresh = np.quantile(np.abs(poly), quantile)
    stock_thresh = np.quantile(np.abs(stock), quantile)
    poly_moved = np.abs(poly) >= poly_thresh
    stock_moved = np.abs(stock) >= stock_thresh

    both = int((poly_moved & stock_moved).sum())
    poly_only = int((poly_moved & ~stock_moved).sum())
    stock_only = int((~poly_moved & stock_moved).sum())
    neither = int((~poly_moved & ~stock_moved).sum())
    n = len(poly)

    return {
        "quantile_used": quantile,
        "poly_threshold_abs_log_odds": float(poly_thresh),
        "stock_threshold_abs_log_return": float(stock_thresh),
        "both_moved": both,
        "poly_moved_stock_didnt": poly_only,
        "stock_moved_poly_didnt": stock_only,
        "neither_moved": neither,
        "n": n,
        "pct_both_moved": both / n if n else None,
        # Given stock moved materially, how often did Polymarket also move?
        "pct_poly_moved_given_stock_moved": (both / (both + stock_only)) if (both + stock_only) else None,
    }


def _corr(x: pd.Series, y: pd.Series) -> dict:
    if len(x) < 3 or x.nunique() <= 1 or y.nunique() <= 1:
        return {"n": len(x), "spearman_rho": None, "spearman_p": None,
                "pearson_r": None, "pearson_p": None, "degenerate": True}
    rho, p_s = spearmanr(x, y)
    r, p_p = pearsonr(x, y)
    return {
        "n": len(x), "spearman_rho": float(rho), "spearman_p": float(p_s),
        "pearson_r": float(r), "pearson_p": float(p_p), "degenerate": False,
    }


def part_a_main_benchmark(stock_lookup: dict, universe_df: pd.DataFrame) -> dict:
    """Does Polymarket's own 24h reaction track the real stock's reaction?"""
    if not SHOCK_PATH.exists():
        return {"status": "skipped", "reason": f"{SHOCK_PATH} not found"}

    df = pd.read_parquet(
        SHOCK_PATH,
        columns=["article_id", "market_id", "category", "split", "canonical_ts", "y_logit_24h",
                 "y_logit_24h_ladder", "valid_24h"],
    )
    df = df[df["valid_24h"] == True].copy()
    df["market_id"] = df["market_id"].astype(str)

    mkt_to_cid = universe_df.set_index(universe_df["market_id"].astype(str))["company_id"]
    df["company_id"] = df["market_id"].map(mkt_to_cid)
    df = df.dropna(subset=["company_id", "canonical_ts", "y_logit_24h"])
    df["canonical_ts"] = pd.to_datetime(df["canonical_ts"], unit="s", utc=True).dt.tz_localize(None)

    # Pre-event Polymarket probability (p0): needed for a price-level/boundary-
    # compression interaction term (Snowberg & Wolfers 2010 favorite-longshot
    # bias; Wolfers & Zitzewitz 2004) -- only lives in tuples.parquet, joined
    # here by (article_id, market_id). tuples.parquet also carries group_id
    # for the same (article_id, market_id) pair, which is the join key
    # matching_ablation.parquet needs -- pulled here too so script 26 can use
    # Thread 1's own match-quality score (embedding_score) as a moderator of
    # the stock-reaction relationship: a signal no outside literature could
    # suggest, since it's unique to this project's matching pipeline.
    if TUPLES_PATH.exists():
        price_df = pd.read_parquet(
            TUPLES_PATH, columns=["article_id", "market_id", "group_id", "price_at_article"]
        )
        price_df["market_id"] = price_df["market_id"].astype(str)
        price_df = price_df.drop_duplicates(subset=["article_id", "market_id"])
        df = df.merge(price_df, on=["article_id", "market_id"], how="left")
    else:
        df["price_at_article"] = np.nan
        df["group_id"] = np.nan

    if MATCHING_ABLATION_PATH.exists():
        scores_df = pd.read_parquet(
            MATCHING_ABLATION_PATH, columns=["article_id", "group_id", "embedding_score", "joint_score"]
        ).drop_duplicates(subset=["article_id", "group_id"])
        df = df.merge(scores_df, on=["article_id", "group_id"], how="left")
    else:
        df["embedding_score"] = np.nan
        df["joint_score"] = np.nan

    rows = []
    for _, row in df.iterrows():
        cid = str(row["company_id"])
        prices = stock_lookup.get(cid)
        if prices is None:
            continue
        ret = _bracket_log_return(prices, row["canonical_ts"])
        if ret is None:
            continue
        rows.append({
            "company_id": cid, "category": row["category"], "split": row["split"],
            "y_logit_24h": row["y_logit_24h"],
            "y_logit_24h_ladder": row["y_logit_24h_ladder"],
            "stock_log_return": ret,
            "price_at_article": row.get("price_at_article"),
            "embedding_score": row.get("embedding_score"),
            "joint_score": row.get("joint_score"),
        })

    joined = pd.DataFrame(rows)
    if joined.empty:
        return {"status": "no_overlap", "n_valid_24h_rows": len(df), "n_companies_with_stock_data": len(stock_lookup)}

    result = {
        "status": "ok",
        "n_valid_24h_rows": len(df),
        "n_joined_to_real_stock_data": len(joined),
        "n_companies_with_stock_data": len(stock_lookup),
        "signed_correlation_raw_target": _corr(joined["y_logit_24h"], joined["stock_log_return"]),
        "magnitude_correlation_raw_target": _corr(joined["y_logit_24h"].abs(), joined["stock_log_return"].abs()),
        "signed_correlation_ladder_target": _corr(joined["y_logit_24h_ladder"].dropna(),
                                                    joined.loc[joined["y_logit_24h_ladder"].notna(), "stock_log_return"]),
        "material_move_table": _material_move_table(joined["y_logit_24h"].to_numpy(), joined["stock_log_return"].to_numpy()),
    }

    # Simple OLS: y_logit_24h ~ stock_log_return
    x = joined["stock_log_return"].to_numpy()
    y = joined["y_logit_24h"].to_numpy()
    if len(x) >= 3 and np.std(x) > 0:
        slope, intercept = np.polyfit(x, y, 1)
        pred = slope * x + intercept
        ss_res = np.sum((y - pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None
        result["ols_poly_on_stock"] = {"slope": float(slope), "intercept": float(intercept), "r2": r2}

    # Per-category breakdown (small-n categories will just show low n, reported honestly)
    per_cat = {}
    for cat, grp in joined.groupby("category"):
        per_cat[str(cat)] = {
            "n": len(grp),
            "magnitude_correlation": _corr(grp["y_logit_24h"].abs(), grp["stock_log_return"].abs()),
        }
    result["per_category"] = per_cat

    joined.to_parquet(Path("results/public_market_benchmark_rows.parquet"), index=False)
    return result


def part_b_thread1_external_validation(stock_lookup: dict, universe_df: pd.DataFrame) -> dict:
    """Does the Thread 1 matching score ALSO predict the real stock's reaction size,
    not just Polymarket's own (the only thing novel_math_design.md's acceptance
    test checked)?"""
    if not MATCHING_ABLATION_PATH.exists() or not TUPLES_PATH.exists() or not CONTRACT_GROUPS_PATH.exists():
        return {"status": "skipped", "reason": "matching_ablation.parquet / tuples.parquet / contract_groups.parquet not found"}

    scores = pd.read_parquet(MATCHING_ABLATION_PATH)
    tuples_dates = pd.read_parquet(TUPLES_PATH, columns=["article_id", "canonical_ts"]).drop_duplicates(subset=["article_id"])
    groups = pd.read_parquet(CONTRACT_GROUPS_PATH, columns=["group_id", "company_name"])

    # company_name -> company_id via universe_df (classify_company_contract sets both
    # from the same COMPANY_DICT canonical key, so a direct name match is safe here).
    name_to_cid = universe_df[["company_name", "company_id"]].drop_duplicates().set_index("company_name")["company_id"]

    scores = scores.merge(tuples_dates, on="article_id", how="left")
    scores = scores.merge(groups, on="group_id", how="left")
    scores["company_id"] = scores["company_name"].map(name_to_cid)
    scores = scores.dropna(subset=["canonical_ts", "company_id"])
    scores["canonical_ts"] = pd.to_datetime(scores["canonical_ts"], unit="s", utc=True).dt.tz_localize(None)

    rows = []
    for _, row in scores.iterrows():
        cid = str(row["company_id"])
        prices = stock_lookup.get(cid)
        if prices is None:
            continue
        ret = _bracket_log_return(prices, row["canonical_ts"])
        if ret is None:
            continue
        rows.append({
            "embedding_score": row.get("embedding_score"),
            "joint_score": row.get("joint_score"),
            "stock_log_return_abs": abs(ret),
        })

    joined = pd.DataFrame(rows)
    if joined.empty:
        return {"status": "no_overlap", "n_scored_pairs": len(scores)}

    return {
        "status": "ok",
        "n_scored_pairs": len(scores),
        "n_joined_to_real_stock_data": len(joined),
        "embedding_score_vs_real_stock_reaction": _corr(joined["embedding_score"], joined["stock_log_return_abs"]),
        "joint_score_vs_real_stock_reaction": _corr(joined["joint_score"], joined["stock_log_return_abs"]),
        "note": (
            "Compare to the Polymarket-internal validation already reported: "
            "joint_score vs Polymarket's OWN |y_logit_24h| was rho=0.509. "
            "This is the same joint_score against an external benchmark instead."
        ),
    }


def part_c_thread2_external_validation(stock_lookup: dict, universe_df: pd.DataFrame) -> dict:
    """Does the ladder-corrected target align BETTER or WORSE with the real
    stock's reaction than the raw target does? A different question from the
    CV-predictive-fit test already reported (scripts/16b), using an external
    anchor instead of Polymarket's own held-out data."""
    if not SHOCK_PATH.exists():
        return {"status": "skipped", "reason": f"{SHOCK_PATH} not found"}

    df = pd.read_parquet(
        SHOCK_PATH,
        columns=["market_id", "category", "canonical_ts", "y_logit_24h",
                 "y_logit_24h_ladder", "valid_24h"],
    )
    df = df[df["valid_24h"] == True].copy()
    df["market_id"] = df["market_id"].astype(str)
    mkt_to_cid = universe_df.set_index(universe_df["market_id"].astype(str))["company_id"]
    df["company_id"] = df["market_id"].map(mkt_to_cid)
    df = df.dropna(subset=["company_id", "canonical_ts", "y_logit_24h", "y_logit_24h_ladder"])
    df["canonical_ts"] = pd.to_datetime(df["canonical_ts"], unit="s", utc=True).dt.tz_localize(None)

    rows = []
    for _, row in df.iterrows():
        cid = str(row["company_id"])
        prices = stock_lookup.get(cid)
        if prices is None:
            continue
        ret = _bracket_log_return(prices, row["canonical_ts"])
        if ret is None:
            continue
        rows.append({
            "category": row["category"],
            "y_logit_24h": row["y_logit_24h"],
            "y_logit_24h_ladder": row["y_logit_24h_ladder"],
            "stock_log_return": ret,
        })

    joined = pd.DataFrame(rows)
    if joined.empty:
        return {"status": "no_overlap"}

    by_category = {}
    for cat, grp in joined.groupby("category"):
        by_category[str(cat)] = {
            "n": len(grp),
            "raw_vs_stock": _corr(grp["y_logit_24h"], grp["stock_log_return"]),
            "ladder_vs_stock": _corr(grp["y_logit_24h_ladder"], grp["stock_log_return"]),
        }

    return {
        "status": "ok",
        "n_joined": len(joined),
        "overall_raw_vs_stock": _corr(joined["y_logit_24h"], joined["stock_log_return"]),
        "overall_ladder_vs_stock": _corr(joined["y_logit_24h_ladder"], joined["stock_log_return"]),
        "by_category": by_category,
    }


def main() -> None:
    if not STOCKS_PATH.exists():
        print(f"{STOCKS_PATH} not found — run scripts/22_pull_public_stock_prices.py first.")
        return
    if not UNIVERSE_PATH.exists():
        print(f"{UNIVERSE_PATH} not found.")
        return

    stocks_df = pd.read_parquet(STOCKS_PATH)
    stock_lookup = _build_stock_lookup(stocks_df)
    universe_df = pd.read_parquet(UNIVERSE_PATH, columns=["market_id", "company_id", "company_name"])

    log.info("benchmark_start", n_companies_with_stock_data=len(stock_lookup))

    result = {
        "part_a_main_benchmark": part_a_main_benchmark(stock_lookup, universe_df),
        "part_b_thread1_external_validation": part_b_thread1_external_validation(stock_lookup, universe_df),
        "part_c_thread2_external_validation": part_c_thread2_external_validation(stock_lookup, universe_df),
    }

    Path("results").mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps(result, indent=2, default=str))
    print(f"\nWritten: {OUT_PATH}")


if __name__ == "__main__":
    main()
