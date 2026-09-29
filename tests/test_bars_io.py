"""Tests for src/utils/bars_io.py."""

import pandas as pd

from src.utils import bars_io


def _write_bars(tmp_path, market_id: str) -> None:
    part_dir = tmp_path / "contract_family=price_ladder" / "year=2025"
    part_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "ts_min": [1_700_000_000, 1_700_000_060],
        "close_lo": [0.1, 0.2],
        "volume_usdc": [100.0, 200.0],
    })
    df.to_parquet(part_dir / f"part-{market_id}.parquet")


def test_load_bars_found(tmp_path, monkeypatch):
    monkeypatch.setattr(bars_io, "BARS_DIR", tmp_path)
    bars_io.load_bars.cache_clear()
    _write_bars(tmp_path, "market-abc")

    df = bars_io.load_bars("market-abc")
    assert list(df["ts_min"]) == [1_700_000_000, 1_700_000_060]
    assert list(df["close_lo"]) == [0.1, 0.2]


def test_load_bars_missing_market_returns_empty_with_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(bars_io, "BARS_DIR", tmp_path)
    bars_io.load_bars.cache_clear()

    df = bars_io.load_bars("does-not-exist")
    assert df.empty
    assert list(df.columns) == ["ts_min", "close_lo", "volume_usdc"]


def test_load_bars_is_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(bars_io, "BARS_DIR", tmp_path)
    bars_io.load_bars.cache_clear()
    _write_bars(tmp_path, "market-cached")

    first = bars_io.load_bars("market-cached")

    # Delete the backing file — a cache hit must not need to re-scan/re-read it.
    for f in tmp_path.rglob("part-market-cached.parquet"):
        f.unlink()

    second = bars_io.load_bars("market-cached")
    pd.testing.assert_frame_equal(first, second)
