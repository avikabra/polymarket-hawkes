"""Tests for src/analysis/reaction_windows.py."""

import pandas as pd
import pytest

from src.analysis.reaction_windows import compute_reaction_windows


def _make_bars(prices: list[float], start_ts: int = 0) -> pd.DataFrame:
    """Build a minimal bars DataFrame: one bar per minute starting at start_ts."""
    return pd.DataFrame([
        {"ts_min": start_ts + i * 60, "close_lo": p, "volume_usdc": 1000.0}
        for i, p in enumerate(prices)
    ])


def test_simple_6h_window():
    # 7 hours of bars at 1-min resolution
    n = 7 * 60
    base_ts = 1_700_000_000
    prices = [float(i) * 0.01 for i in range(n)]  # linearly increasing
    bars = _make_bars(prices, start_ts=base_ts)

    article_ts = pd.Timestamp(base_ts, unit="s", tz="UTC")
    result = compute_reaction_windows(
        article_ts=article_ts,
        timestamp_precision="minute",
        market_resolved_at=None,
        bars_df=bars,
        window_hours=[1, 6, 24],
    )

    # LOCF carries last bar forward → all windows are valid when market_resolved_at=None
    assert result["valid_1h"] is True
    assert result["valid_6h"] is True
    assert result["valid_24h"] is True  # LOCF: last bar's price carried to 24h mark

    # 6h = 360 min; close_lo(base_ts + 360*60) - close_lo(base_ts) = 3.60 - 0.0
    assert abs(result["y_logit_6h"] - 3.60) < 0.01


def test_day_precision_blocks_short_windows():
    n = 2 * 24 * 60  # 2 days of bars
    base_ts = 1_700_000_000
    bars = _make_bars([0.0] * n, start_ts=base_ts)
    article_ts = pd.Timestamp(base_ts, unit="s", tz="UTC")

    result = compute_reaction_windows(
        article_ts=article_ts,
        timestamp_precision="day",
        market_resolved_at=None,
        bars_df=bars,
        window_hours=[1, 6, 24],
    )
    assert result["valid_1h"] is False
    assert result["valid_6h"] is False
    assert result["valid_24h"] is True


def test_market_resolved_before_window_end():
    n = 3 * 60
    base_ts = 1_700_000_000
    bars = _make_bars([0.0] * n, start_ts=base_ts)
    article_ts = pd.Timestamp(base_ts, unit="s", tz="UTC")
    # Market resolved 2 hours after article — blocks 6h window
    resolved_at = pd.Timestamp(base_ts + 2 * 3600, unit="s", tz="UTC")

    result = compute_reaction_windows(
        article_ts=article_ts,
        timestamp_precision="minute",
        market_resolved_at=resolved_at,
        bars_df=bars,
        window_hours=[1, 6, 24],
    )
    assert result["valid_1h"] is True
    assert result["valid_6h"] is False
    assert result["valid_24h"] is False


def test_no_article_ts():
    bars = _make_bars([0.5] * 100)
    result = compute_reaction_windows(
        article_ts=None,
        timestamp_precision="minute",
        market_resolved_at=None,
        bars_df=bars,
        window_hours=[1, 6, 24],
    )
    for dh in [1, 6, 24]:
        assert result[f"valid_{dh}h"] is False
        assert result[f"y_logit_{dh}h"] is None
