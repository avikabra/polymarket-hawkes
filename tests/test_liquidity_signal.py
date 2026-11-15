"""Tests for src/matching/liquidity_signal.py."""

import pandas as pd
import pytest

from src.matching.liquidity_signal import (
    compute_liquidity_baseline,
    compute_liquidity_response,
)

_BASE_TS = 1_700_000_000  # arbitrary fixed epoch-second anchor


def _flat_bars(start_ts: int, n_days: int, daily_volume: float) -> pd.DataFrame:
    """One bar per day (bar granularity doesn't matter to volume sums)."""
    return pd.DataFrame([
        {"ts_min": start_ts + i * 86400, "close_lo": 0.0, "volume_usdc": daily_volume}
        for i in range(n_days)
    ])


def _hourly_bars(start_ts: int, n_hours: int, hourly_volume: float) -> pd.DataFrame:
    return pd.DataFrame([
        {"ts_min": start_ts + i * 3600, "close_lo": 0.0, "volume_usdc": hourly_volume}
        for i in range(n_hours)
    ])


def test_spike_after_article_has_larger_volume_z_than_flat_control():
    trailing_days = 14
    hourly_rate = 100.0 / 24.0  # normal, steady rate -> 100/day baseline
    baseline_start = _BASE_TS - trailing_days * 24 * 3600

    # Control: the same steady hourly rate continues straight through the
    # response window too — nothing abnormal happens at article_ts.
    control_bars = _hourly_bars(baseline_start, trailing_days * 24 + 1, hourly_rate)

    # Spike case: identical baseline, but a large volume bar lands just after
    # article_ts (inside the 1h response window for minute precision).
    spike_bars = pd.concat([
        _hourly_bars(baseline_start, trailing_days * 24, hourly_rate),
        pd.DataFrame([{"ts_min": _BASE_TS + 60, "close_lo": 0.0, "volume_usdc": 50_000.0}]),
    ], ignore_index=True)

    article_ts = pd.Timestamp(_BASE_TS, unit="s", tz="UTC")

    control = compute_liquidity_response(
        member_bars={"m1": control_bars},
        article_ts=article_ts,
        timestamp_precision="minute",
    )
    spike = compute_liquidity_response(
        member_bars={"m1": spike_bars},
        article_ts=article_ts,
        timestamp_precision="minute",
    )

    assert spike["volume_z"] > control["volume_z"] + 10  # materially larger
    assert control["volume_z"] == pytest.approx(0.0, abs=1e-6)


def test_day_precision_never_gets_subday_window():
    bars = _flat_bars(_BASE_TS - 20 * 86400, 20, daily_volume=100.0)
    article_ts = pd.Timestamp(_BASE_TS, unit="s", tz="UTC")

    result = compute_liquidity_response(
        member_bars={"m1": bars},
        article_ts=article_ts,
        timestamp_precision="day",
        minute_precision_window_hours=1,  # would be used if precision were ignored
    )
    assert result["window_hours_used"] == 24


def test_minute_precision_gets_tight_window():
    bars = _flat_bars(_BASE_TS - 20 * 86400, 20, daily_volume=100.0)
    article_ts = pd.Timestamp(_BASE_TS, unit="s", tz="UTC")

    result = compute_liquidity_response(
        member_bars={"m1": bars},
        article_ts=article_ts,
        timestamp_precision="minute",
        minute_precision_window_hours=1,
    )
    assert result["window_hours_used"] == 1


def test_baseline_never_leaks_future_data():
    """A fixture where data at/after before_ts would change the answer if leaked."""
    trailing_days = 14
    before_ts = _BASE_TS
    baseline_start = before_ts - trailing_days * 86400

    bars_no_future = _flat_bars(baseline_start, trailing_days, daily_volume=100.0)
    baseline_no_future = compute_liquidity_baseline(
        bars_no_future, before_ts=before_ts, trailing_days=trailing_days
    )

    # Same trailing window, plus a huge volume bar exactly at before_ts and another
    # well after it — both must be excluded from the baseline.
    bars_with_future = pd.concat([
        bars_no_future,
        pd.DataFrame([
            {"ts_min": before_ts, "close_lo": 0.0, "volume_usdc": 1_000_000.0},
            {"ts_min": before_ts + 3600, "close_lo": 0.0, "volume_usdc": 1_000_000.0},
        ]),
    ], ignore_index=True)
    baseline_with_future = compute_liquidity_baseline(
        bars_with_future, before_ts=before_ts, trailing_days=trailing_days
    )

    assert baseline_with_future["baseline_median"] == pytest.approx(
        baseline_no_future["baseline_median"]
    )
    assert baseline_with_future["baseline_std"] == pytest.approx(
        baseline_no_future["baseline_std"]
    )


def test_baseline_excludes_data_exactly_at_before_ts():
    """The day bucket touching before_ts is half-open: [before_ts-86400, before_ts)."""
    before_ts = _BASE_TS
    bars = pd.DataFrame([{"ts_min": before_ts, "close_lo": 0.0, "volume_usdc": 999.0}])
    baseline = compute_liquidity_baseline(bars, before_ts=before_ts, trailing_days=1)
    assert baseline["baseline_median"] == pytest.approx(0.0)
