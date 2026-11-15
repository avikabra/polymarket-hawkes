"""Monotone strike-ladder joint correction of reaction windows, per
novel_math_design.md Thread 2, Formula (Q1, Option C).

Monotonicity of P(event) in strike price only holds within a
(group_id, end_at, strike_direction) cohort — contract_groups.parquet's
group_id (company x metric x expiry-month) is coarser than a true ladder;
103/158 ladder groups span multiple end_at values and 66/158 mix
strike_direction (see novel_math_design.md "Grounding facts").

For each such cohort, each member market's independently-computed
y_logit_{Delta}h (from reaction_windows.compute_reaction_windows) is jointly
corrected by projecting the cohort's valid values onto the monotone cone via
weighted isotonic regression (PAVA). This is a genuine joint estimate, not
post-hoc smoothing: each corrected value is a function of every other valid
sibling's observed reaction in the cohort (via PAVA's pooling), not of its
own value alone.

All values stay in log-odds space (y_logit_*) throughout this module — never
converted to raw [0,1] probability, per CLAUDE.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

# Columns that must all be present for a row to share a real ladder cohort
# with other rows. A row missing any of these (e.g. corporate_event, which
# has no ladder at all) has no monotonicity structure to exploit and gets a
# singleton cohort of itself instead of an error — see build_ladder_cohorts.
_COHORT_KEY_COLS = ["group_id", "end_at", "strike_price", "strike_direction"]


def build_ladder_cohorts(tuples_df: pd.DataFrame) -> pd.Series:
    """Return a cohort_id per row of tuples_df, indexed like tuples_df.

    Real cohorts group rows by (group_id, end_at, strike_direction) — the
    grain within which strike-price monotonicity actually holds. Rows missing
    strike_price and/or strike_direction cannot share that structure with any
    other row and get their own singleton cohort, keyed by row index, rather
    than being dropped or raising: every row gets a cohort_id.
    """
    has_ladder_info = tuples_df[_COHORT_KEY_COLS].notna().all(axis=1)

    cohort_id = pd.Series(index=tuples_df.index, dtype=object)

    real = tuples_df.loc[has_ladder_info]
    if not real.empty:
        cohort_id.loc[real.index] = (
            "cohort::"
            + real["group_id"].astype(str)
            + "::"
            + real["end_at"].astype(str)
            + "::"
            + real["strike_direction"].astype(str)
        )

    singleton_idx = tuples_df.index[~has_ladder_info]
    if len(singleton_idx) > 0:
        cohort_id.loc[singleton_idx] = "singleton::" + singleton_idx.astype(str)

    return cohort_id


def compute_ladder_adjusted_reactions(
    tuples_df: pd.DataFrame, window_hours: list[int]
) -> pd.DataFrame:
    """Add ladder-corrected reaction columns for each window in window_hours.

    For each Delta in window_hours, adds two columns:
      y_logit_{Delta}h_ladder        the isotonic-corrected log-odds reaction
      ladder_n_members_used_{Delta}h diagnostic: valid siblings used in the fit

    For each cohort (see build_ladder_cohorts) and window, takes the member
    rows with valid_{Delta}h == True, sorts by strike_price, and fits
    IsotonicRegression(increasing=(strike_direction == "below")) weighted by
    volume_24h_usdc. Fitted values are written back as y_logit_{Delta}h_ladder
    for those rows; ladder_n_members_used_{Delta}h records how many valid
    siblings (the row itself included) went into that fit.

    A row is passed through unchanged (y_logit_{Delta}h_ladder =
    y_logit_{Delta}h, an explicit no-op, not a null) whenever there is no real
    joint correction to compute for it: a singleton cohort, a cohort with
    fewer than 2 valid members for that window, or the row itself being
    invalid for that window (excluded from the fit so it can't corrupt the
    isotonic curve, per novel_math_design.md). ladder_n_members_used_{Delta}h
    is 0 for a row with no valid reaction that window, 1 for a valid row with
    no valid siblings (PAVA of one point is itself, so passthrough is exact),
    and the true sibling count otherwise.

    tuples_df must have columns: group_id, end_at, strike_price,
    strike_direction, volume_24h_usdc, and y_logit_{Delta}h/valid_{Delta}h
    for each Delta in window_hours. Never touches raw [0,1] probabilities.
    """
    df = tuples_df.copy()
    df["_cohort_id"] = build_ladder_cohorts(df)

    for delta_h in window_hours:
        key_y = f"y_logit_{delta_h}h"
        key_v = f"valid_{delta_h}h"
        key_ladder = f"{key_y}_ladder"
        key_n = f"ladder_n_members_used_{delta_h}h"

        if key_y not in df.columns or key_v not in df.columns:
            continue

        ladder_vals = df[key_y].copy()
        n_used = pd.Series(0, index=df.index, dtype=int)

        for _, group in df.groupby("_cohort_id"):
            valid_mask = group[key_v].fillna(False).astype(bool)
            valid_group = group.loc[valid_mask]
            n_valid = len(valid_group)

            if n_valid == 0:
                continue  # no valid reaction this window; n_used stays 0
            if n_valid == 1:
                # No siblings to jointly correct with — PAVA of a single
                # point is itself, so the passthrough default is exact.
                n_used.loc[valid_group.index] = 1
                continue

            strike_direction = str(group["strike_direction"].iloc[0])
            increasing = strike_direction == "below"

            sorted_valid = valid_group.sort_values("strike_price")
            x = sorted_valid["strike_price"].to_numpy(dtype=float)
            y = sorted_valid[key_y].to_numpy(dtype=float)
            w = sorted_valid["volume_24h_usdc"].fillna(0.0).to_numpy(dtype=float)
            if w.sum() <= 0:
                # Degenerate all-zero/missing weights: fall back to uniform
                # weighting rather than letting IsotonicRegression divide by
                # a zero total weight.
                w = np.ones_like(w)

            iso = IsotonicRegression(increasing=increasing, out_of_bounds="clip")
            y_fit = iso.fit_transform(x, y, sample_weight=w)

            ladder_vals.loc[sorted_valid.index] = y_fit
            n_used.loc[sorted_valid.index] = n_valid

        df[key_ladder] = ladder_vals
        df[key_n] = n_used

    df = df.drop(columns=["_cohort_id"])
    return df
