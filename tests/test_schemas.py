import math
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas import NewsEvent, Trade


def _trade(**kwargs):
    defaults = dict(
        market_id="0xabc",
        token_id="0x1",
        ts_s=1700000000,
        log_index=0,
        price_raw=0.5,
        log_odds=0.0,
        size_usdc=100.0,
        side="YES_BUY",
        tx_hash="0xdeadbeef",
    )
    return Trade(**(defaults | kwargs))


def _event(**kwargs):
    defaults = dict(
        event_id="e1",
        market_id="0xabc",
        canonical_ts=datetime(2024, 9, 1, 12, 0, tzinfo=timezone.utc),
        timestamp_precision="minute",
        included_in_hawkes_likelihood=False,
        directional_impact=1,
        magnitude=0.5,
        member_article_ids=["a1"],
        member_count=1,
        sources=["espn"],
    )
    return NewsEvent(**(defaults | kwargs))


def test_trade_correct_log_odds():
    t = _trade(price_raw=0.5, log_odds=0.0)
    assert abs(t.log_odds) < 1e-9


def test_trade_price_zero_rejected():
    with pytest.raises(ValidationError):
        _trade(price_raw=0.0, log_odds=-999.0)


def test_trade_price_one_rejected():
    with pytest.raises(ValidationError):
        _trade(price_raw=1.0, log_odds=999.0)


def test_news_event_day_precision_hawkes_rejected():
    with pytest.raises(ValidationError):
        _event(timestamp_precision="day", included_in_hawkes_likelihood=True)


def test_news_event_minute_precision_hawkes_passes():
    e = _event(timestamp_precision="minute", included_in_hawkes_likelihood=True)
    assert e.included_in_hawkes_likelihood is True
