from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas import NewsEvent, Trade, VerifiedArticle


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
        member_article_ids=["a1"],
        member_count=1,
        sources=["espn"],
        consensus_directional_impact=1,
        dominant_news_type="quantitative",
    )
    return NewsEvent(**(defaults | kwargs))


def _verified(**kwargs):
    defaults = dict(
        article_id="a1",
        market_id="0xabc",
        event_id="e1",
        is_match=True,
        match_strength=0.85,
        directional_impact=1,
        magnitude=0.6,
        news_type="quantitative",
        embedding_source="full_text",
    )
    return VerifiedArticle(**(defaults | kwargs))


# Trade tests

def test_trade_correct_log_odds():
    t = _trade(price_raw=0.5, log_odds=0.0)
    assert abs(t.log_odds) < 1e-9


def test_trade_price_zero_rejected():
    with pytest.raises(ValidationError):
        _trade(price_raw=0.0, log_odds=-999.0)


def test_trade_price_one_rejected():
    with pytest.raises(ValidationError):
        _trade(price_raw=1.0, log_odds=999.0)


# NewsEvent tests (D4 schema — no Hawkes fields)

def test_news_event_has_no_hawkes_field():
    e = _event()
    assert not hasattr(e, "included_in_hawkes_likelihood")
    assert not hasattr(e, "hawkes_eligible")


def test_news_event_day_precision_allowed():
    # Day precision is fine — no hawkes constraint in D4
    e = _event(timestamp_precision="day")
    assert e.timestamp_precision == "day"


def test_news_event_consensus_directional_impact_validated():
    with pytest.raises(ValidationError):
        _event(consensus_directional_impact=2)  # must be -1, 0, or 1


def test_news_event_dominant_news_type_stored():
    e = _event(dominant_news_type="high_attention")
    assert e.dominant_news_type == "high_attention"


# VerifiedArticle tests

def test_verified_article_roundtrip():
    va = _verified()
    dumped = va.model_dump()
    restored = VerifiedArticle(**dumped)
    assert restored.article_id == va.article_id
    assert restored.news_type == "quantitative"


def test_verified_article_invalid_news_type():
    with pytest.raises(ValidationError):
        _verified(news_type="random_string")


def test_verified_article_invalid_directional_impact():
    with pytest.raises(ValidationError):
        _verified(directional_impact=2)


def test_verified_article_assembly_fields_default_none():
    va = _verified()
    assert va.price_at_article is None
    assert va.y_logit_6h is None
    assert va.valid_6h is False
