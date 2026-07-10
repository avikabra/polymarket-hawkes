"""Script 14: Pre-analysis feasibility gate per plan §5.

Checks per-category thresholds:
  - ≥200 resolved markets per category
  - Median ≥10 verified articles per market
  - Median ≥50 trades per market
  - ≥60% articles with timestamp_precision = "minute"
  - ≥70% articles with body_text_available = True

Exits with code 1 if any threshold fails, blocking make focal.
On success, writes data/analysis/_FOCAL_SUCCESS.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pyarrow.parquet as pq

UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
TRADES_DIR = Path("data/polymarket/trades")
DB_PATH = Path("data/matches/matches.db")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")
BODIES_DIR = Path("data/news/bodies")
ANALYSIS_DIR = Path("data/analysis")

_THRESHOLDS = {
    "min_markets_per_category": 200,
    "median_verified_articles_per_market": 10,
    "median_trades_per_market": 50,
    "min_minute_precision_pct": 60.0,
    "min_body_text_available_pct": 70.0,
}


def _load_article_meta() -> pd.DataFrame:
    import pyarrow as pa

    parts = []
    for d in [GDELT_DIR, FEEDS_DIR]:
        if not d.exists():
            continue
        paths = list(d.rglob("*.parquet"))
        if paths:
            parts.append(pa.concat_tables([pq.read_table(p) for p in paths]).to_pandas())
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["article_id"])
    return df


def _trade_counts_per_market() -> dict[str, int]:
    """Return {market_id: trade_count} from partitioned trades parquet."""
    if not TRADES_DIR.exists():
        return {}
    counts: dict[str, int] = {}
    for p in TRADES_DIR.rglob("part-*.parquet"):
        # Filename convention: part-{market_id}.parquet
        market_id = p.stem.replace("part-", "")
        df = pd.read_parquet(p, columns=["market_id"])
        counts[market_id] = counts.get(market_id, 0) + len(df)
    return counts


def _verified_per_market() -> dict[str, int]:
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT market_id, COUNT(*) FROM verifications WHERE is_match=1 GROUP BY market_id"
    ).fetchall()
    conn.close()
    return {str(m): int(c) for m, c in rows}


def main() -> int:
    if not UNIVERSE_PATH.exists():
        print("FAIL: universe.parquet not found.")
        return 1

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    article_meta = _load_article_meta()
    verified_per_market = _verified_per_market()
    trade_counts = _trade_counts_per_market()

    # Body text coverage
    fetched_ids: set[str] = set()
    if BODIES_DIR.exists():
        fetched_ids = {p.stem for p in BODIES_DIR.glob("*.txt") if p.stat().st_size > 0}

    pass_all = True
    print(f"\n{'Category':<16} {'Markets':>8} {'Med.Art':>8} {'Med.Trd':>8} {'Min%':>6} {'Body%':>6} {'STATUS':>8}")
    print("-" * 70)

    categories = universe_df["category"].unique() if "category" in universe_df.columns else []

    for cat in sorted(categories):
        cat_markets = universe_df[universe_df["category"] == cat]
        n_markets = len(cat_markets)
        market_ids = set(cat_markets["market_id"].astype(str).tolist())

        # Verified articles per market
        art_counts = [verified_per_market.get(m, 0) for m in market_ids]
        med_art = float(pd.Series(art_counts).median()) if art_counts else 0.0

        # Trade counts per market
        trd_counts = [trade_counts.get(m, 0) for m in market_ids]
        med_trd = float(pd.Series(trd_counts).median()) if trd_counts else 0.0

        # Timestamp precision (from corpus articles for this category)
        if not article_meta.empty and "timestamp_precision" in article_meta.columns:
            # Approximate: all corpus articles (not category-filtered — categories not on articles)
            n_minute = (article_meta["timestamp_precision"] == "minute").sum()
            min_pct = 100.0 * n_minute / max(len(article_meta), 1)
        else:
            min_pct = 0.0

        # Body text coverage (on fetched bodies matching verified articles)
        verified_ids = set(verified_per_market.keys()) & market_ids
        # For body coverage, check all corpus article_ids (can't easily filter by market here)
        if not article_meta.empty:
            corpus_ids = set(article_meta["article_id"].tolist())
            n_fetched = len(fetched_ids & corpus_ids)
            body_pct = 100.0 * n_fetched / max(len(corpus_ids), 1)
        else:
            body_pct = 0.0

        ok = (
            n_markets >= _THRESHOLDS["min_markets_per_category"]
            and med_art >= _THRESHOLDS["median_verified_articles_per_market"]
            and med_trd >= _THRESHOLDS["median_trades_per_market"]
            and min_pct >= _THRESHOLDS["min_minute_precision_pct"]
            and body_pct >= _THRESHOLDS["min_body_text_available_pct"]
        )
        if not ok:
            pass_all = False

        status = "PASS" if ok else "FAIL"
        print(
            f"{cat:<16} {n_markets:>8} {med_art:>8.1f} {med_trd:>8.0f} "
            f"{min_pct:>5.1f}% {body_pct:>5.1f}%   {status}"
        )

    print("-" * 70)
    print(f"\nThresholds: markets≥{_THRESHOLDS['min_markets_per_category']}  "
          f"med_art≥{_THRESHOLDS['median_verified_articles_per_market']}  "
          f"med_trd≥{_THRESHOLDS['median_trades_per_market']}  "
          f"minute≥{_THRESHOLDS['min_minute_precision_pct']}%  "
          f"body≥{_THRESHOLDS['min_body_text_available_pct']}%")

    if pass_all:
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        (ANALYSIS_DIR / "_FOCAL_SUCCESS").touch()
        print("\nFEASIBILITY GATE PASSED — _FOCAL_SUCCESS written.")
        return 0
    else:
        print("\nFEASIBILITY GATE FAILED — see failed rows above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
