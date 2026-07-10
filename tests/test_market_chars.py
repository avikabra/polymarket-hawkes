"""Tests for src/analysis/market_chars.py."""

import pandas as pd
import pytest

from src.analysis.market_chars import compute_market_chars


def _make_bars(
    prices: list[float],
    volumes: list[float] | None = None,
    start_ts: int = 1_700_000_000,
) -> pd.DataFrame:
    if volumes is None:
        volumes = [100.0] * len(prices)
    return pd.DataFrame([
        {"ts_min": start_ts + i * 60, "close_lo": p, "volume_usdc": v}
        for i, (p, v) in enumerate(zip(prices, volumes))
    ])


def test_price_at_article_locf():
    base_ts = 1_700_000_000
    # 10 bars with linear price
    bars = _make_bars([float(i) * 0.1 for i in range(10)], start_ts=base_ts)
    article_ts = pd.Timestamp(base_ts + 5 * 60, unit="s", tz="UTC")

    chars = compute_market_chars(
        article_ts=article_ts,
        market_resolved_at=None,
        category="nfl",
        bars_df=bars,
        prior_article_count=3,
    )
    assert chars["price_at_article"] == pytest.approx(0.5, abs=0.001)
    assert chars["category"] == "nfl"
    assert chars["prior_article_count"] == 3


def test_volume_24h_window():
    base_ts = 1_700_000_000
    n = 25 * 60  # 25 hours
    bars = _make_bars([0.0] * n, volumes=[10.0] * n, start_ts=base_ts)
    # Article at t = base_ts + 24h (exactly 24h after start)
    article_ts = pd.Timestamp(base_ts + 24 * 3600, unit="s", tz="UTC")

    chars = compute_market_chars(
        article_ts=article_ts,
        market_resolved_at=None,
        category="nba",
        bars_df=bars,
        prior_article_count=0,
    )
    # 24h * 60 min = 1440 bars × 10 USDC = 14400
    assert chars["volume_24h_usdc"] == pytest.approx(14400.0, rel=0.01)


def test_time_to_resolution():
    base_ts = 1_700_000_000
    bars = _make_bars([0.5] * 10, start_ts=base_ts)
    article_ts = pd.Timestamp(base_ts, unit="s", tz="UTC")
    resolved_at = pd.Timestamp(base_ts + 2 * 86400, unit="s", tz="UTC")

    chars = compute_market_chars(
        article_ts=article_ts,
        market_resolved_at=resolved_at,
        category="politics",
        bars_df=bars,
        prior_article_count=0,
    )
    assert chars["time_to_resolution_days"] == pytest.approx(2.0, abs=0.01)


def test_no_article_ts_returns_nones():
    bars = _make_bars([0.5] * 10)
    chars = compute_market_chars(
        article_ts=None,
        market_resolved_at=None,
        category="geopolitics",
        bars_df=bars,
        prior_article_count=5,
    )
    assert chars["price_at_article"] is None
    assert chars["time_to_resolution_days"] is None
    assert chars["prior_article_count"] == 5
