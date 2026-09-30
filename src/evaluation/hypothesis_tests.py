"""H1-H4 hypothesis test statistics (plan §4.4)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# H1: shock R² > raw R² (linear baseline, pooled)
# ---------------------------------------------------------------------------

def compute_h1(metrics_df: pd.DataFrame, bootstrap_df: pd.DataFrame) -> dict:
    """H1: shock R² > raw R² (linear baseline, pooled).

    Expects metrics_df to have rows with columns:
      model_type ("shock"|"raw"), arch ("linear"), category ("all"), r2_oos.
    Expects bootstrap_df to have columns:
      model_type, arch, category, ci_lower, ci_upper.

    Returns dict: {delta_r2, ci_lower, ci_upper, supported}.
    """
    def _get_r2(model_type: str) -> float:
        mask = (
            (metrics_df["model_type"] == model_type)
            & (metrics_df["arch"] == "linear")
            & (metrics_df["category"] == "all")
        )
        rows = metrics_df[mask]
        if rows.empty:
            raise KeyError(f"No metrics row for model_type={model_type!r}, arch=linear, category=all")
        return float(rows["r2_oos"].iloc[0])

    def _get_ci(model_type: str) -> tuple[float, float]:
        mask = (
            (bootstrap_df["model_type"] == model_type)
            & (bootstrap_df["arch"] == "linear")
            & (bootstrap_df["category"] == "all")
        )
        rows = bootstrap_df[mask]
        if rows.empty:
            return (float("nan"), float("nan"))
        return float(rows["ci_lower"].iloc[0]), float(rows["ci_upper"].iloc[0])

    r2_shock = _get_r2("shock")
    r2_raw = _get_r2("raw")
    delta_r2 = r2_shock - r2_raw

    ci_shock = _get_ci("shock")
    ci_raw = _get_ci("raw")
    delta_ci_lower = ci_shock[0] - ci_raw[1]
    delta_ci_upper = ci_shock[1] - ci_raw[0]

    return {
        "hypothesis": "H1",
        "r2_shock": r2_shock,
        "r2_raw": r2_raw,
        "delta_r2": delta_r2,
        "ci_lower": delta_ci_lower,
        "ci_upper": delta_ci_upper,
        "supported": bool(delta_ci_lower > 0),
    }


# ---------------------------------------------------------------------------
# H2: best architecture differs by category
# ---------------------------------------------------------------------------

# purging.py's _CAT_ORDER (the closed-set schema domain, from the contract_family
# Literal in src/schemas/market.py) also declares "other_ladder" and "other" —
# these 5 are the categories actually observed with real rows in the corpus as
# of the 2026-09-29 Bouchet run (scripts/14_feasibility_gate.py's per-category
# output never showed them). Verify against real data before trusting this list
# if the universe has since been expanded (see novel_math_design.md item 5).
_CATEGORIES = ["corporate_event", "price_ladder", "revenue_ladder", "valuation_ladder", "market_cap_ladder"]


def compute_h2(metrics_df: pd.DataFrame, bootstrap_df: pd.DataFrame) -> dict:
    """H2: best architecture differs by category.

    Returns 5x3 R² matrix (rows=categories, cols=archs) + per-column winner
    + whether CIs for the best-performing category's winning arch and the
    worst-performing category's winning arch (by R²) are non-overlapping.
    """
    categories = _CATEGORIES
    archs = ["lstm", "transformer", "tcn"]

    r2_matrix: dict[str, dict[str, float]] = {}
    for cat in categories:
        r2_matrix[cat] = {}
        for arch in archs:
            mask = (
                (metrics_df["category"] == cat)
                & (metrics_df["arch"] == arch)
                & (metrics_df["model_type"] == "shock")
            )
            rows = metrics_df[mask]
            r2_matrix[cat][arch] = float(rows["r2_oos"].iloc[0]) if not rows.empty else float("nan")

    # Best arch per category
    winners: dict[str, str] = {}
    for cat in categories:
        vals = r2_matrix[cat]
        best_arch = max(vals, key=lambda a: vals[a] if not np.isnan(vals[a]) else -np.inf)
        winners[cat] = best_arch

    archs_differ = len(set(winners.values())) > 1

    # CI non-overlap check: best-performing category's winning arch vs
    # worst-performing category's winning arch (by R²).
    def _get_ci(cat: str, arch: str) -> tuple[float, float]:
        mask = (
            (bootstrap_df["category"] == cat)
            & (bootstrap_df["arch"] == arch)
            & (bootstrap_df["model_type"] == "shock")
        )
        rows = bootstrap_df[mask]
        if rows.empty:
            return (float("nan"), float("nan"))
        return float(rows["ci_lower"].iloc[0]), float(rows["ci_upper"].iloc[0])

    winning_r2 = {cat: r2_matrix[cat][winners[cat]] for cat in categories}
    best_category = max(winning_r2, key=lambda c: winning_r2[c] if not np.isnan(winning_r2[c]) else -np.inf)
    worst_category = min(winning_r2, key=lambda c: winning_r2[c] if not np.isnan(winning_r2[c]) else np.inf)

    best_arch = winners[best_category]
    worst_arch = winners[worst_category]
    ci_best = _get_ci(best_category, best_arch)
    ci_worst = _get_ci(worst_category, worst_arch)

    cis_non_overlapping = (
        ci_best[1] < ci_worst[0] or ci_worst[1] < ci_best[0]
    )

    return {
        "hypothesis": "H2",
        "r2_matrix": r2_matrix,
        "winners": winners,
        "archs_differ": archs_differ,
        "best_category": best_category,
        "worst_category": worst_category,
        "ci_best": {"lower": ci_best[0], "upper": ci_best[1]},
        "ci_worst": {"lower": ci_worst[0], "upper": ci_worst[1]},
        "cis_non_overlapping": cis_non_overlapping,
        "supported": bool(archs_differ and cis_non_overlapping),
    }


# ---------------------------------------------------------------------------
# H3: quantitative R² > high_attention R² (linear baseline)
# ---------------------------------------------------------------------------

def compute_h3(linear_test_df: pd.DataFrame) -> dict:
    """H3: quantitative news R² > high_attention news R² (linear baseline).

    linear_test_df must have columns: y_true, y_pred, news_type,
    directional_impact.

    news_type == "quantitative" identifies quantitative articles.
    directional_impact in {-1, 1} identifies high-attention articles.
    """
    from src.evaluation.metrics import compute_r2_oos

    quant_mask = linear_test_df["news_type"] == "quantitative"
    high_att_mask = linear_test_df["directional_impact"].isin([-1, 1])

    def _r2(mask: pd.Series) -> float:
        sub = linear_test_df[mask]
        if len(sub) < 2:
            return float("nan")
        return compute_r2_oos(sub["y_true"].to_numpy(), sub["y_pred"].to_numpy())

    r2_quant = _r2(quant_mask)
    r2_high_att = _r2(high_att_mask)
    delta_r2 = r2_quant - r2_high_att

    return {
        "hypothesis": "H3",
        "r2_quantitative": r2_quant,
        "r2_high_attention": r2_high_att,
        "delta_r2": delta_r2,
        "n_quantitative": int(quant_mask.sum()),
        "n_high_attention": int(high_att_mask.sum()),
        "supported": bool(delta_r2 > 0),
    }


# ---------------------------------------------------------------------------
# H4: best ladder category R² > corporate_event R² using best arch per category
# ---------------------------------------------------------------------------

_LADDER_CATEGORIES = [c for c in _CATEGORIES if c != "corporate_event"]


def compute_h4(metrics_df: pd.DataFrame, bootstrap_df: pd.DataFrame) -> dict:
    """H4: best-of-the-ladder-categories R² > corporate_event R², using best arch per category.

    Among the ladder categories (price_ladder, revenue_ladder, valuation_ladder,
    market_cap_ladder), picks whichever single category achieves the highest
    R² with its best arch (no aggregation across ladder categories), then
    compares its CI against corporate_event's CI.
    """

    def _best_r2(cat: str) -> tuple[str, float]:
        mask = (
            (metrics_df["category"] == cat)
            & (metrics_df["model_type"] == "shock")
        )
        sub = metrics_df[mask]
        if sub.empty:
            return ("", float("nan"))
        best_row = sub.loc[sub["r2_oos"].idxmax()]
        return str(best_row["arch"]), float(best_row["r2_oos"])

    def _get_ci(cat: str, arch: str) -> tuple[float, float]:
        mask = (
            (bootstrap_df["category"] == cat)
            & (bootstrap_df["arch"] == arch)
            & (bootstrap_df["model_type"] == "shock")
        )
        rows = bootstrap_df[mask]
        if rows.empty:
            return (float("nan"), float("nan"))
        return float(rows["ci_lower"].iloc[0]), float(rows["ci_upper"].iloc[0])

    ladder_results = {cat: _best_r2(cat) for cat in _LADDER_CATEGORIES}
    best_ladder_category = max(
        ladder_results,
        key=lambda c: ladder_results[c][1] if not np.isnan(ladder_results[c][1]) else -np.inf,
    )
    best_arch_best_ladder, r2_best_ladder = ladder_results[best_ladder_category]
    best_arch_corporate_event, r2_corporate_event = _best_r2("corporate_event")
    delta_r2 = r2_best_ladder - r2_corporate_event

    ci_best_ladder = _get_ci(best_ladder_category, best_arch_best_ladder)
    ci_corporate_event = _get_ci("corporate_event", best_arch_corporate_event)
    delta_ci_lower = ci_best_ladder[0] - ci_corporate_event[1]
    delta_ci_upper = ci_best_ladder[1] - ci_corporate_event[0]

    return {
        "hypothesis": "H4",
        "best_ladder_category": best_ladder_category,
        "r2_best_ladder": r2_best_ladder,
        "r2_corporate_event": r2_corporate_event,
        "best_arch_best_ladder": best_arch_best_ladder,
        "best_arch_corporate_event": best_arch_corporate_event,
        "delta_r2": delta_r2,
        "ci_lower": delta_ci_lower,
        "ci_upper": delta_ci_upper,
        "supported": bool(delta_ci_lower > 0),
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all_hypothesis_tests(
    metrics_path: str,
    bootstrap_path: str,
    output_path: str,
    linear_test_path: str | None = None,
) -> dict:
    """Load results, run H1-H4, write JSON to output_path.

    Args:
        metrics_path: path to results/metrics_all.parquet.
        bootstrap_path: path to results/bootstrap_cis.parquet.
        output_path: where to write the JSON summary.
        linear_test_path: optional parquet with columns
            y_true, y_pred, news_type, directional_impact (for H3).

    Returns:
        dict with keys h1, h2, h3, h4.
    """
    metrics_df = pd.read_parquet(metrics_path)
    bootstrap_df = pd.read_parquet(bootstrap_path)

    results: dict[str, Any] = {}

    results["h1"] = compute_h1(metrics_df, bootstrap_df)
    results["h2"] = compute_h2(metrics_df, bootstrap_df)

    if linear_test_path is not None:
        linear_test_df = pd.read_parquet(linear_test_path)
        results["h3"] = compute_h3(linear_test_df)
    else:
        results["h3"] = {"hypothesis": "H3", "supported": None, "note": "linear_test_path not provided"}

    results["h4"] = compute_h4(metrics_df, bootstrap_df)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"Hypothesis test results written to {output_path}")

    return results
