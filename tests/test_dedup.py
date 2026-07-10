"""Tests for src/matching/dedup.py."""

from datetime import datetime, timezone, timedelta

import numpy as np
import pytest

from src.matching.dedup import cluster_market


def _make_row(
    article_id: str,
    market_id: str = "m1",
    pub_at: str = "2024-09-01T12:00:00+00:00",
    precision: str = "minute",
    directional_impact: int = 0,
    news_type: str = "qualitative",
) -> dict:
    return {
        "market_id": market_id,
        "article_id": article_id,
        "article_published_at": pub_at,
        "timestamp_precision": precision,
        "directional_impact": directional_impact,
        "news_type": news_type,
        "raw_metadata_json": "{}",
    }


def test_single_article_yields_one_event():
    rows = [_make_row("a1")]
    events = cluster_market(rows, emb_map={})
    assert len(events) == 1
    assert events[0].member_count == 1
    assert events[0].member_article_ids == ["a1"]


def test_articles_within_4h_merge():
    base = "2024-09-01T12:00:00+00:00"
    near = "2024-09-01T13:30:00+00:00"
    rows = [_make_row("a1", pub_at=base), _make_row("a2", pub_at=near)]
    events = cluster_market(rows, emb_map={})
    assert len(events) == 1
    assert events[0].member_count == 2


def test_articles_more_than_4h_apart_do_not_merge():
    base = "2024-09-01T12:00:00+00:00"
    far = "2024-09-01T17:00:00+00:00"  # 5h later
    rows = [_make_row("a1", pub_at=base), _make_row("a2", pub_at=far)]
    events = cluster_market(rows, emb_map={})
    assert len(events) == 2


def test_cosine_below_threshold_prevents_merge():
    base = "2024-09-01T12:00:00+00:00"
    near = "2024-09-01T12:30:00+00:00"
    dim = 16

    # Two orthogonal embeddings → cosine = 0 < 0.85
    emb_a = np.zeros(dim, dtype=np.float16)
    emb_b = np.zeros(dim, dtype=np.float16)
    emb_a[0] = 1.0
    emb_b[1] = 1.0

    rows = [_make_row("a1", pub_at=base), _make_row("a2", pub_at=near)]
    events = cluster_market(rows, emb_map={"a1": emb_a, "a2": emb_b})
    assert len(events) == 2


def test_high_cosine_within_4h_merges():
    base = "2024-09-01T12:00:00+00:00"
    near = "2024-09-01T12:10:00+00:00"
    dim = 16

    # Nearly identical embeddings → cosine ≈ 1.0
    emb_a = np.ones(dim, dtype=np.float16)
    emb_b = np.ones(dim, dtype=np.float16)
    emb_b[0] = 1.01  # tiny perturbation

    rows = [_make_row("a1", pub_at=base), _make_row("a2", pub_at=near)]
    events = cluster_market(rows, emb_map={"a1": emb_a, "a2": emb_b})
    assert len(events) == 1


def test_canonical_ts_prefers_minute_precision():
    # a1 is day precision, a2 is minute — canonical_ts should come from a2
    base = "2024-09-01T12:00:00+00:00"
    rows = [
        _make_row("a1", pub_at=base, precision="day"),
        _make_row("a2", pub_at=base, precision="minute"),
    ]
    events = cluster_market(rows, emb_map={})
    assert events[0].timestamp_precision == "minute"


def test_empty_input_returns_empty():
    events = cluster_market([], emb_map={})
    assert events == []
