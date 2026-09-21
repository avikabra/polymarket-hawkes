import hashlib
from datetime import datetime, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.news.normalizer import build_matching_text_corpus, normalize_and_deduplicate


def _row(url: str, source: str, precision: str, published_at=None) -> dict:
    return dict(
        article_id=hashlib.sha256(url.encode()).hexdigest(),
        source=source,
        url=url,
        published_at=published_at,
        timestamp_precision=precision,
        title="Test",
        lede=None, body_text=None, body_text_available=False,
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


def _gdelt_row(url: str, entities=None, themes=None) -> dict:
    r = _row(url, "gdelt", "day")
    r["title"] = url  # GDELT placeholder: title == url
    r["entities"] = entities or ["Apple Inc", "Tim Cook"]
    r["themes"] = themes or ["ECON_STOCKMARKET", "TAX_FNCACT"]
    return r


def _rss_row(url: str, title: str, lede: str) -> dict:
    r = _row(url, "espn", "minute", published_at=_DT)
    r["title"] = title
    r["lede"] = lede
    return r


def test_build_matching_text_corpus_gdelt_row_gets_synthetic_title(tmp_path):
    gdelt_dir = tmp_path / "gdelt_gkg"
    feeds_dir = tmp_path / "feeds"
    gdelt_dir.mkdir()
    feeds_dir.mkdir()

    gdelt_url = "https://example.com/gdelt-article"
    gdelt_df = pd.DataFrame([_gdelt_row(gdelt_url)])
    pq.write_table(pa.Table.from_pandas(gdelt_df), gdelt_dir / "part-0.parquet")

    result = build_matching_text_corpus(str(gdelt_dir), str(feeds_dir))
    row = result[result["url"] == gdelt_url].iloc[0]
    assert row["title"] != gdelt_url
    assert "gdelt" in row["title"]  # source domain
    assert "apple inc" in row["title"].lower() or "Apple Inc" in row["title"]


def test_build_matching_text_corpus_rss_row_keeps_real_title(tmp_path):
    gdelt_dir = tmp_path / "gdelt_gkg"
    feeds_dir = tmp_path / "feeds"
    gdelt_dir.mkdir()
    feeds_dir.mkdir()

    rss_url = "https://espn.com/rss-article"
    rss_title = "Chiefs win thriller in overtime"
    rss_df = pd.DataFrame([_rss_row(rss_url, rss_title, "Kansas City wins.")])
    pq.write_table(pa.Table.from_pandas(rss_df), feeds_dir / "part-0.parquet")

    result = build_matching_text_corpus(str(gdelt_dir), str(feeds_dir))
    row = result[result["url"] == rss_url].iloc[0]
    assert row["title"] == rss_title
    assert row["lede"] == "Kansas City wins."


def test_build_matching_text_corpus_empty_dirs_returns_empty(tmp_path):
    result = build_matching_text_corpus(str(tmp_path / "nope1"), str(tmp_path / "nope2"))
    assert result.empty
