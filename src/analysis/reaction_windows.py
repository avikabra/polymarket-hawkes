"""Compute log-odds reaction windows for verified articles.

For each verified article at time t_i in market k:
  y_logit_Δ = close_lo(t_i + Δ) - close_lo(t_i)

where close_lo is read from the 1-min bars (LOCF interpolation).

Validity rules per plan §0.3:
  - valid_Δ = False if market resolved before t_i + Δ
  - valid_Δ = False if timestamp_precision == "day" and Δ < 24h
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd


def _locf_lookup(bars_df: pd.DataFrame, ts_s: int) -> float | None:
    """Return the last-observation-carried-forward close_lo at or before ts_s.

    bars_df must be sorted by ts_min ascending (or will be sorted here).
    """
    before = bars_df[bars_df["ts_min"] <= ts_s].sort_values("ts_min")
    if before.empty:
        return None
    return float(before.iloc[-1]["close_lo"])


def compute_reaction_windows(
    article_ts: pd.Timestamp | None,
    timestamp_precision: str,
    market_resolved_at: pd.Timestamp | None,
    bars_df: pd.DataFrame,
    window_hours: list[int],
) -> dict:
    """Return dict with y_logit_{Δ}h and valid_{Δ}h for each window.

    bars_df must have columns: ts_min (int, epoch-sec), close_lo (float, log-odds).
    """
    result: dict = {}

    for delta_h in window_hours:
        key_y = f"y_logit_{delta_h}h"
        key_v = f"valid_{delta_h}h"

        # Day-precision articles can only anchor 24h windows
        if timestamp_precision == "day" and delta_h < 24:
            result[key_y] = None
            result[key_v] = False
            continue

        if article_ts is None:
            result[key_y] = None
            result[key_v] = False
            continue

        ts_i = int(article_ts.timestamp())
        ts_end = ts_i + delta_h * 3600

        # Exclude if market resolved before t_i + Δ
        if market_resolved_at is not None:
            resolved_ts = int(market_resolved_at.timestamp())
            if resolved_ts < ts_end:
                result[key_y] = None
                result[key_v] = False
                continue

        lo_start = _locf_lookup(bars_df, ts_i)
        lo_end = _locf_lookup(bars_df, ts_end)

        if lo_start is None or lo_end is None:
            result[key_y] = None
            result[key_v] = False
        else:
            result[key_y] = float(lo_end - lo_start)
            result[key_v] = True

    return result
