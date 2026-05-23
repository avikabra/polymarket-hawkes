import asyncio
import tempfile

import duckdb

from src.utils import DiskCache, TokenBucket, register_parquet_views


def test_token_bucket_immediate_when_full():
    bucket = TokenBucket(rate=1.0, capacity=10.0)
    asyncio.get_event_loop().run_until_complete(bucket.acquire(1.0))


def test_disk_cache_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = DiskCache(tmpdir)
        cache.set("https://example.com/data?q=1", b"hello world")
        result = cache.get("https://example.com/data?q=1")
    assert result == b"hello world"


def test_register_parquet_views_missing_path_no_raise():
    conn = duckdb.connect(":memory:")
    paths_config = {
        "polymarket": {"trades": "/nonexistent/path/trades"},
        "news": {"gdelt_gkg": "/nonexistent/path/gdelt"},
    }
    register_parquet_views(conn, paths_config)  # must not raise
