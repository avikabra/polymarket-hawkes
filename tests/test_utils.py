import asyncio
import os
import tempfile
import time

import duckdb

from src.utils import DiskCache, TokenBucket, register_parquet_views


def test_token_bucket_immediate_when_full():
    bucket = TokenBucket(rate=1.0, capacity=10.0)
    asyncio.run(bucket.acquire(1.0))


def test_disk_cache_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = DiskCache(tmpdir)
        cache.set("https://example.com/data?q=1", b"hello world")
        result = cache.get("https://example.com/data?q=1")
    assert result == b"hello world"


def test_disk_cache_no_ttl_never_expires():
    # Default (no max_age_seconds) preserves old no-expiry behavior, so
    # existing callers (BigQuery, Gamma, Goldsky/Data-API) are unaffected.
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = DiskCache(tmpdir)
        cache.set("key", b"value")
        p = cache._path("key")
        old_time = time.time() - 1_000_000
        os.utime(p, (old_time, old_time))
        assert cache.get("key") == b"value"


def test_disk_cache_ttl_fresh_entry_is_hit():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = DiskCache(tmpdir)
        cache.set("key", b"value")
        assert cache.get("key", max_age_seconds=3600) == b"value"


def test_disk_cache_ttl_expired_entry_is_miss():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = DiskCache(tmpdir)
        cache.set("key", b"value")
        p = cache._path("key")
        old_time = time.time() - 7200
        os.utime(p, (old_time, old_time))
        assert cache.get("key", max_age_seconds=3600) is None


def test_register_parquet_views_missing_path_no_raise():
    conn = duckdb.connect(":memory:")
    paths_config = {
        "polymarket": {"trades": "/nonexistent/path/trades"},
        "news": {"gdelt_gkg": "/nonexistent/path/gdelt"},
    }
    register_parquet_views(conn, paths_config)  # must not raise
