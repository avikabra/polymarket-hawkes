"""Liquidity signal for Thread 1 joint matching (novel_math_design.md "Liquidity
signal (Q2)"): abnormal trading volume relative to each market's own trailing
baseline, plus realized price impact, around a verified article's timestamp.

Two stages:
  compute_liquidity_baseline  — one market's trailing volume median/std, strictly
                                 backward-looking (mirrors market_chars.py's
                                 volume_24h_usdc no-leakage discipline).
  compute_liquidity_response  — a group's abnormal-volume z-score (summed across
                                 member markets) and max |price_impact| (via
                                 reaction_windows.compute_reaction_windows, reused
                                 not reimplemented), respecting day-precision.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.reaction_windows import compute_reaction_windows

# Floor applied to baseline_std before dividing, so a flat/zero-volume trailing
# window (baseline_std == 0) doesn't produce a division by zero. Anything but a
# true zero-variance baseline exceeds this by orders of magnitude in practice.
_STD_FLOOR = 1e-6


def compute_liquidity_baseline(
    bars_df: pd.DataFrame,
    before_ts: int,
    trailing_days: int = 14,
) -> dict:
    """Median/std of daily trading volume over `trailing_days` strictly before
    `before_ts` (epoch seconds).

    Backward-looking only: every day bucket ends at or before `before_ts`, and the
    bucket touching `before_ts` is half-open (excludes `before_ts` itself), so this
    never reads data at or after `before_ts` — no future leakage into the baseline.

    bars_df must have columns: ts_min (int, epoch-sec), volume_usdc (float).
    """
    daily_volumes = []
    for day_idx in range(trailing_days):
        day_end = before_ts - day_idx * 86400
        day_start = day_end - 86400
        day_bars = bars_df[(bars_df["ts_min"] >= day_start) & (bars_df["ts_min"] < day_end)]
        daily_volumes.append(float(day_bars["volume_usdc"].sum()))

    arr = np.array(daily_volumes, dtype=float)
    return {
        "baseline_median": float(np.median(arr)),
        "baseline_std": float(np.std(arr)),
        "trailing_days": trailing_days,
    }


def _combined_volume_series(member_bars: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Sum volume_usdc across member markets at each shared ts_min bucket.

    A group's liquidity signal is aggregated by summing raw volume across member
    markets first, then computing one z-score on the combined series — not by
    z-scoring each member separately and summing the z's (those aren't additive
    in a meaningful way without further assumptions). See report for this design
    decision flagged as not fully specified in the plan doc.
    """
    frames = [df[["ts_min", "volume_usdc"]] for df in member_bars.values() if not df.empty]
    if not frames:
        return pd.DataFrame(columns=["ts_min", "volume_usdc"])
    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby("ts_min", as_index=False)["volume_usdc"].sum()


def compute_liquidity_response(
    member_bars: dict[str, pd.DataFrame],
    article_ts: pd.Timestamp | None,
    timestamp_precision: str,
    *,
    market_resolved_at: pd.Timestamp | None = None,
    trailing_days: int = 14,
    minute_precision_window_hours: int = 1,
) -> dict:
    """Abnormal-volume z-score and max |price_impact| for a group's member markets
    around an article's timestamp.

    Respects day-precision (plan §Thread 1 "Liquidity signal"): a day-precision
    article only ever gets a >=24h window, mirroring reaction_windows.py's own
    `timestamp_precision == "day" and delta_h < 24` exclusion rule. Minute-precision
    articles use a tighter window (`minute_precision_window_hours`, default 1h).

    market_resolved_at is optional (not part of the plan doc's stated signature)
    because compute_reaction_windows requires it to exclude windows that extend
    past market resolution; pass it when known, else price_impact is computed
    without that exclusion.

    Returns dict with at least: volume_z, price_impact, window_hours_used.
    """
    window_hours = 24 if timestamp_precision == "day" else minute_precision_window_hours

    if article_ts is None:
        return {"volume_z": 0.0, "price_impact": None, "window_hours_used": window_hours}

    ts_i = int(article_ts.timestamp())
    ts_end = ts_i + window_hours * 3600

    # --- volume_z: sum volume across members, one z-score on the combined series ---
    combined = _combined_volume_series(member_bars)
    baseline = compute_liquidity_baseline(combined, before_ts=ts_i, trailing_days=trailing_days)
    window_bars = combined[(combined["ts_min"] >= ts_i) & (combined["ts_min"] < ts_end)]
    volume_in_window = float(window_bars["volume_usdc"].sum())

    # compute_liquidity_baseline reports *daily* (24h) volume stats (per its own
    # spec), but volume_in_window is summed over `window_hours`, which is <24h
    # for minute-precision articles. Comparing a sub-day window sum directly
    # against a 24h baseline would make every minute-precision article look like
    # a huge volume deficit even under normal conditions. Not specified in the
    # plan doc — the simplest fix (and the one used here) is to linearly scale
    # the daily baseline down to the window's duration before differencing;
    # window_hours=24 (the day-precision / primary corpus case) makes this a
    # no-op, so this only affects the minute-precision branch.
    scale = window_hours / 24.0
    baseline_median = baseline["baseline_median"] * scale
    baseline_std = baseline["baseline_std"] * scale

    std = max(baseline_std, _STD_FLOOR)
    volume_z = (volume_in_window - baseline_median) / std

    # --- price_impact: max |y_logit| across members, reusing reaction_windows ---
    impacts = []
    key_y = f"y_logit_{window_hours}h"
    for bars_df in member_bars.values():
        if bars_df.empty:
            continue
        windows = compute_reaction_windows(
            article_ts=article_ts,
            timestamp_precision=timestamp_precision,
            market_resolved_at=market_resolved_at,
            bars_df=bars_df,
            window_hours=[window_hours],
        )
        y = windows.get(key_y)
        if y is not None:
            impacts.append(abs(y))

    price_impact = max(impacts) if impacts else None

    return {
        "volume_z": float(volume_z),
        "price_impact": price_impact,
        "window_hours_used": window_hours,
    }
