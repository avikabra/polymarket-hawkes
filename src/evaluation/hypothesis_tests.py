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

def compute_h2(metrics_df: pd.DataFrame, bootstrap_df: pd.DataFrame) -> dict:
    """H2: best architecture differs by category.

    Returns 4x3 R² matrix (rows=categories, cols=archs) + per-column winner
    + whether CIs for sports winner and geopolitics winner are non-overlapping.
    """
    categories = ["sports", "politics", "geopolitics"]
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

    # CI non-overlap check: sports winner vs geopolitics winner
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

    sports_arch = winners.get("sports", archs[0])
    geo_arch = winners.get("geopolitics", archs[0])
    ci_sports = _get_ci("sports", sports_arch)
    ci_geo = _get_ci("geopolitics", geo_arch)

    cis_non_overlapping = (
        ci_sports[1] < ci_geo[0] or ci_geo[1] < ci_sports[0]
    )

    return {
        "hypothesis": "H2",
        "r2_matrix": r2_matrix,
        "winners": winners,
        "archs_differ": archs_differ,
        "ci_sports": {"lower": ci_sports[0], "upper": ci_sports[1]},
        "ci_geopolitics": {"lower": ci_geo[0], "upper": ci_geo[1]},
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
# H4: geopolitics R² > sports R² using best arch per category
# ---------------------------------------------------------------------------

def compute_h4(metrics_df: pd.DataFrame, bootstrap_df: pd.DataFrame) -> dict:
    """H4: geopolitics R² > sports R² using best arch per category."""

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

    geo_arch, r2_geo = _best_r2("geopolitics")
    sports_arch, r2_sports = _best_r2("sports")
    delta_r2 = r2_geo - r2_sports

    ci_geo = _get_ci("geopolitics", geo_arch)
    ci_sports = _get_ci("sports", sports_arch)
    delta_ci_lower = ci_geo[0] - ci_sports[1]
    delta_ci_upper = ci_geo[1] - ci_sports[0]

    return {
        "hypothesis": "H4",
        "r2_geopolitics": r2_geo,
        "r2_sports": r2_sports,
        "best_arch_geopolitics": geo_arch,
        "best_arch_sports": sports_arch,
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
