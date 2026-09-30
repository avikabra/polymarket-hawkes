"""Pure correlation computation for the Thread 1 matching ablation
(novel_math_design.md "Validation (Q3) — REQUIRED, not optional").

Kept separate from scripts/09b_matching_ablation.py (which does the DB/bars I/O)
so the actual statistic can be unit-tested against synthetic scores/reactions
without matches.db or real bars data.
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import spearmanr

from src.matching.joint_verifier import _logit, _sigmoid


def compute_score_reaction_correlations(df: pd.DataFrame) -> dict:
    """Spearman correlation of embedding-only score and joint score against the
    realized |y_logit_24h| reaction.

    df must have columns: embedding_score, joint_score, realized_abs_y_logit_24h.
    Rows where realized_abs_y_logit_24h is null are dropped first — per
    novel_math_design.md's Fix 1, y_logit_24h is the only real target in this
    corpus (1h/6h have ~0% coverage), so only pairs with an achievable 24h window
    contribute to the correlation.

    Returns a dict with, for each of "embedding" and "joint":
      {name}_rho, {name}_p, n_used, and a top-level "degenerate" flag (True if
      fewer than 3 usable rows, or all ranks tied — Spearman is undefined/trivial
      in that case, per the plan doc's "must not be ... degenerate" requirement).
    """
    usable = df.dropna(subset=["realized_abs_y_logit_24h"])
    n_used = len(usable)

    degenerate = (
        n_used < 3
        or usable["realized_abs_y_logit_24h"].nunique() <= 1
        or usable["embedding_score"].nunique() <= 1
    )

    result: dict = {"n_used": n_used, "n_total": len(df), "degenerate": degenerate}

    for name, col in [("embedding", "embedding_score"), ("joint", "joint_score")]:
        if degenerate or usable[col].nunique() <= 1:
            result[f"{name}_rho"] = float("nan")
            result[f"{name}_p"] = float("nan")
            continue
        rho, p = spearmanr(usable[col], usable["realized_abs_y_logit_24h"])
        result[f"{name}_rho"] = float(rho)
        result[f"{name}_p"] = float(p)

    return result


def compute_single_score_correlation(scores: pd.Series, reactions: pd.Series) -> dict:
    """Spearman correlation of one arbitrary score column against realized
    |y_logit_24h| reactions.

    Generalizes compute_score_reaction_correlations (above) for the Thread 1
    weight-tuning grid search (scripts/09c_tune_matching_weights.py), which
    needs a correlation for many candidate (w1, w2) scores, not just the two
    fixed "embedding"/"joint" columns that function is shaped around. Same
    degenerate-case handling (fewer than 3 usable rows, or all-tied ranks).
    """
    df = pd.DataFrame({"score": scores, "reaction": reactions}).dropna()
    n_used = len(df)
    degenerate = (
        n_used < 3
        or df["reaction"].nunique() <= 1
        or df["score"].nunique() <= 1
    )
    if degenerate:
        return {"rho": float("nan"), "p": float("nan"), "n_used": n_used, "degenerate": True}
    rho, p = spearmanr(df["score"], df["reaction"])
    return {"rho": float(rho), "p": float(p), "n_used": n_used, "degenerate": False}


def match_quality_score(
    embedding_score: pd.Series, liquidity_z: pd.Series, w1: float, w2: float
) -> pd.Series:
    """match_strength = sigmoid(w1*logit(embedding_score) + w2*liquidity_z) —
    vectorized over a Series, reusing joint_verifier.py's exact per-pair formula
    (same _logit/_sigmoid) rather than reimplementing it.
    """
    logit_emb = embedding_score.apply(_logit)
    raw = w1 * logit_emb + w2 * liquidity_z
    return raw.apply(_sigmoid)


def grid_search_weights(
    embedding_score: pd.Series,
    liquidity_z: pd.Series,
    realized: pd.Series,
    weight_grid: list[float],
) -> pd.DataFrame:
    """Try every (w1, w2) in weight_grid x weight_grid; return one row per
    combination with columns w1, w2, rho, p, n_used, degenerate, sorted by rho
    descending (NaN/degenerate rows last).

    Pure — no I/O. The caller supplies already-loaded score components (see
    scripts/09c_tune_matching_weights.py), so this can run in a unit test
    against synthetic series without matches.db or real bars data.
    """
    rows = []
    for w1 in weight_grid:
        for w2 in weight_grid:
            score = match_quality_score(embedding_score, liquidity_z, w1, w2)
            stats = compute_single_score_correlation(score, realized)
            rows.append({"w1": w1, "w2": w2, **stats})
    return (
        pd.DataFrame(rows)
        .sort_values("rho", ascending=False, na_position="last")
        .reset_index(drop=True)
    )
