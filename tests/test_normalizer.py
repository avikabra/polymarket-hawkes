import hashlib
from datetime import datetime, timezone

import pandas as pd
import pytest

from src.news.normalizer import normalize_and_deduplicate


def _row(url: str, source: str, precision: str, published_at=None) -> dict:
    return dict(
        article_id=hashlib.sha256(url.encode()).hexdigest(),
        source=source,
        url=url,
        published_at=published_at,
        timestamp_precision=precision,
        title="Test",
        lede=None, body_text=None, text_available=False,
        entities=[], themes=[], raw_metadata_json="{}",
    )


_DT = datetime(2024, 8, 1, 12, 0, tzinfo=timezone.utc)
_URL = "https://example.com/article"


def test_feed_beats_gdelt_for_same_url():
    gdelt_df = pd.DataFrame([_row(_URL, "gdelt", "day")])
    feed_df = pd.DataFrame([_row(_URL, "espn", "minute", published_at=_DT)])
    result = normalize_and_deduplicate(gdelt_df, feed_df)
    assert len(result) == 1
    assert result.iloc[0]["timestamp_precision"] == "minute"
    assert result.iloc[0]["source"] == "espn"


def test_minute_precision_with_no_published_at_raises():
    bad_df = pd.DataFrame([_row(_URL, "espn", "minute", published_at=None)])
    with pytest.raises(ValueError):
        normalize_and_deduplicate(pd.DataFrame(), bad_df)


def test_dedup_reduces_total_count():
    gdelt_df = pd.DataFrame([
        _row(_URL, "gdelt", "day"),
        _row("https://example.com/gdelt-only", "gdelt", "day"),
    ])
    feed_df = pd.DataFrame([
        _row(_URL, "espn", "minute", published_at=_DT),
        _row("https://example.com/feed-only", "espn", "minute", published_at=_DT),
    ])
    result = normalize_and_deduplicate(gdelt_df, feed_df)
    assert len(result) < len(gdelt_df) + len(feed_df)
    assert len(result) == 3  # shared counted once + 2 unique
