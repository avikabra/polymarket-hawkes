"""Shared loader for a market's 1-min bars from the partitioned parquet directory.

Extracted from scripts/12_assemble_dataset.py's `_load_bars` so other modules
(e.g. src/matching/liquidity_signal.py) can reuse the same cached lookup instead
of re-scanning data/polymarket/bars_1min themselves.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd

BARS_DIR = Path("data/polymarket/bars_1min")


@functools.lru_cache(maxsize=None)
def load_bars(market_id: str) -> pd.DataFrame:
    """Load 1-min bars for a market from the partitioned parquet directory.

    Cached: callers (e.g. script 12's fan-out loop) may invoke this many times
    per unique market, and each uncached call does a full BARS_DIR.rglob
    directory scan. Without caching this redundantly re-scans/re-reads the same
    market's bars dozens of times over NFS.
    """
    found = list(BARS_DIR.rglob(f"part-{market_id}.parquet"))
    if not found:
        return pd.DataFrame(columns=["ts_min", "close_lo", "volume_usdc"])
    return pd.read_parquet(found[0])
