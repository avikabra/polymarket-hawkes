"""Pure correlation computation for the Thread 1 matching ablation
(novel_math_design.md "Validation (Q3) — REQUIRED, not optional").

Kept separate from scripts/09b_matching_ablation.py (which does the DB/bars I/O)
so the actual statistic can be unit-tested against synthetic scores/reactions
without matches.db or real bars data.
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import spearmanr


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
