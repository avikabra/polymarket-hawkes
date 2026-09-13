"""Script 12: Assemble the per-article VerifiedArticle dataset.

Joins:
  - matches.db verifications
  - data/polymarket/bars_1min (LOCF reaction windows + market chars)
  - data/polymarket/universe.parquet (market metadata: category, resolved_at)

For each verified (market, article) pair computes:
  - market characteristics vector (x_{k,t_i})
  - reaction windows y_logit_{1h,6h,24h} with validity flags

Writes: data/analysis/tuples.parquet (one row per VerifiedArticle)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.analysis.market_chars import compute_market_chars
from src.analysis.reaction_windows import compute_reaction_windows
from src.utils import assert_covers, get_logger

DB_PATH = Path("data/matches/matches.db")
BARS_DIR = Path("data/polymarket/bars_1min")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
ANALYSIS_DIR = Path("data/analysis")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")

log = get_logger(__name__)


def _load_config() -> dict:
    cfg_path = Path("config/analysis.yaml")
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f)
    return {}


def _load_bars(market_id: str) -> pd.DataFrame:
    """Load 1-min bars for a market from the partitioned parquet directory."""
    found = list(BARS_DIR.rglob(f"part-{market_id}.parquet"))
    if not found:
        return pd.DataFrame(columns=["ts_min", "close_lo", "volume_usdc"])
    return pd.read_parquet(found[0])


def _load_article_meta() -> dict[str, dict]:
    parts = []
    for d in [GDELT_DIR, FEEDS_DIR]:
        if not d.exists():
            continue
        paths = list(d.rglob("*.parquet"))
        if paths:
            parts.append(pa.concat_tables([pq.read_table(p) for p in paths]).to_pandas())
    if not parts:
        return {}
    df = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["article_id"])
    return {
        row["article_id"]: row.to_dict()
        for _, row in df.iterrows()
    }


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    cfg = _load_config()
    window_hours: list[int] = cfg.get("reaction_windows_hours", [1, 6, 24])

    if not DB_PATH.exists():
        print("No matches.db — run scripts 09–10 first.")
        return

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT v.market_id, v.article_id, v.is_match, v.match_strength,
               v.directional_impact, v.magnitude, v.news_type,
               c.article_published_at, c.timestamp_precision,
               ne.event_id
        FROM verifications v
        JOIN candidates c ON v.market_id=c.market_id AND v.article_id=c.article_id
        LEFT JOIN news_events ne ON ne.market_id=v.market_id
            AND json_each.value=v.article_id
            AND json_each.path='$.member_article_ids'
        WHERE v.is_match=1
        """
    ).fetchall()

    if not rows:
        # Fallback: simpler query without event join
        rows = conn.execute(
            """
            SELECT v.market_id, v.article_id, v.is_match, v.match_strength,
                   v.directional_impact, v.magnitude, v.news_type,
                   c.article_published_at, c.timestamp_precision
            FROM verifications v
            JOIN candidates c ON v.market_id=c.market_id AND v.article_id=c.article_id
            WHERE v.is_match=1
            """
        ).fetchall()
        rows = [r + (None,) for r in rows]  # pad event_id

    conn.close()
    log.info("verified pairs", count=len(rows))

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    assert_covers(
        [GDELT_DIR, FEEDS_DIR],
        (cid for cid in universe_df["company_id"] if cid),
        (
            pd.Timestamp(universe_df["created_at"].min()).isoformat(),
            pd.Timestamp(universe_df["end_at"].max()).isoformat(),
        ),
    )
    market_info: dict[str, dict] = {
        str(row["market_id"]): row.to_dict()
        for _, row in universe_df.iterrows()
    }
    article_meta = _load_article_meta()

    # Count prior articles per (market, article) ordered by timestamp
    # Build a prior-count lookup: for each (market, article), count verified articles with earlier ts
    verified_ts: dict[str, dict[str, pd.Timestamp]] = {}  # market_id → {article_id: ts}
    for market_id, article_id, _, _, _, _, _, pub_at, prec, _ in rows:
        if pub_at:
            verified_ts.setdefault(str(market_id), {})[str(article_id)] = pd.Timestamp(pub_at)

    output_rows = []
    for market_id, article_id, is_match, match_strength, di, mag, news_type, pub_at, prec, event_id in rows:
        market_id = str(market_id)
        article_id = str(article_id)

        minfo = market_info.get(market_id, {})
        category = str(minfo.get("category", ""))
        resolved_at_raw = minfo.get("resolved_at")
        resolved_at = pd.Timestamp(resolved_at_raw) if resolved_at_raw else None

        article_ts = pd.Timestamp(pub_at) if pub_at else None
        if article_ts is not None and article_ts.tzinfo is None:
            article_ts = article_ts.tz_localize("UTC")
        if resolved_at is not None and resolved_at.tzinfo is None:
            resolved_at = resolved_at.tz_localize("UTC")

        bars_df = _load_bars(market_id)

        # Prior article count
        mkt_ts_map = verified_ts.get(market_id, {})
        prior_count = sum(
            1 for aid, ts in mkt_ts_map.items()
            if aid != article_id and article_ts is not None and ts < article_ts
        )

        chars = compute_market_chars(
            article_ts=article_ts,
            market_resolved_at=resolved_at,
            category=category,
            bars_df=bars_df,
            prior_article_count=prior_count,
        )

        windows = compute_reaction_windows(
            article_ts=article_ts,
            timestamp_precision=str(prec),
            market_resolved_at=resolved_at,
            bars_df=bars_df,
            window_hours=window_hours,
        )

        # embedding_source will be filled by script 11; default headline_only here
        ameta = article_meta.get(article_id, {})
        embedding_source = "headline_only" if not ameta.get("body_text") else "full_text"

        output_rows.append({
            "article_id": article_id,
            "market_id": market_id,
            "event_id": str(event_id) if event_id else "",
            "is_match": bool(is_match),
            "match_strength": float(match_strength),
            "directional_impact": int(di),
            "magnitude": float(mag),
            "news_type": str(news_type),
            "embedding_source": embedding_source,
            "canonical_ts": int(article_ts.timestamp()) if article_ts is not None else None,
            **chars,
            **windows,
        })

    out_df = pd.DataFrame(output_rows)
    out_path = ANALYSIS_DIR / "tuples.parquet"
    pq.write_table(pa.Table.from_pandas(out_df), out_path)
    log.info("tuples written", rows=len(out_df), path=str(out_path))

    for dh in window_hours:
        valid_col = f"valid_{dh}h"
        if valid_col in out_df.columns:
            n_valid = out_df[valid_col].sum()
            print(f"valid_{dh}h: {n_valid}/{len(out_df)} ({100*n_valid/max(len(out_df),1):.1f}%)")


if __name__ == "__main__":
    main()
