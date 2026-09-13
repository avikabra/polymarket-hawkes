"""Compute the 5-component market characteristics vector x_{k,t_i} per plan §0.5.

Fields:
  price_at_article     logit(P_{k,t_i}) — LOCF close_lo at article time
  time_to_resolution_days  (T_k - t_i) in fractional days
  category             category string ("nfl", "nba", "politics", "geopolitics")
  volume_24h_usdc      sum of volume_usdc in bars over [t_i - 24h, t_i]
  prior_article_count  verified articles for same market with ts < t_i
"""

from __future__ import annotations

import pandas as pd


# TODO W7-9: switch _CATEGORY_ORDER to contract_family values ["monthly_strike","corporate_event"] before running scripts 12-21
_CATEGORY_ORDER = ["nfl", "nba", "politics", "geopolitics"]


def compute_market_chars(
    article_ts: pd.Timestamp | None,
    market_resolved_at: pd.Timestamp | None,
    category: str,
    bars_df: pd.DataFrame,
    prior_article_count: int,
) -> dict:
    """Return market characteristics dict for one (market, article) pair.

    bars_df must have columns: ts_min (int epoch-sec), close_lo (float), volume_usdc (float).
    """
    if article_ts is None:
        return {
            "price_at_article": None,
            "time_to_resolution_days": None,
            "volume_24h_usdc": None,
            "prior_article_count": prior_article_count,
            "category": category,
        }

    ts_i = int(article_ts.timestamp())

    # price_at_article: LOCF close_lo
    before = bars_df[bars_df["ts_min"] <= ts_i].sort_values("ts_min")
    price_at_article = float(before.iloc[-1]["close_lo"]) if not before.empty else None

    # time_to_resolution_days
    if market_resolved_at is not None:
        delta_s = (market_resolved_at.timestamp() - ts_i)
        time_to_resolution_days = float(delta_s / 86400)
    else:
        time_to_resolution_days = None

    # volume_24h_usdc: bars in [t_i - 86400, t_i]
    window_start = ts_i - 86400
    window_bars = bars_df[
        (bars_df["ts_min"] >= window_start) & (bars_df["ts_min"] <= ts_i)
    ]
    volume_24h_usdc = float(window_bars["volume_usdc"].sum())

    return {
        "price_at_article": price_at_article,
        "time_to_resolution_days": time_to_resolution_days,
        "volume_24h_usdc": volume_24h_usdc,
        "prior_article_count": prior_article_count,
        "category": category,
    }
