"""Script 10: Cluster verified articles into NewsEvent records per market.

Reads verifications from matches.db, calls src/matching/dedup.cluster_market,
writes results to news_events table, then writes _EVENTS_SUCCESS.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.matching.dedup import cluster_market
from src.utils import get_logger

DB_PATH = Path("data/matches/matches.db")
MATCHES_DIR = Path("data/matches")
EMBEDDINGS_DIR = Path("data/news/matching_embeddings")
ARTICLE_EMB_PATH = EMBEDDINGS_DIR / "article_embeddings.parquet"

log = get_logger(__name__)


def _load_embeddings() -> dict[str, np.ndarray]:
    if not ARTICLE_EMB_PATH.exists():
        return {}
    df = pq.read_table(ARTICLE_EMB_PATH).to_pandas()
    return {
        row["article_id"]: np.frombuffer(row["embedding"], dtype=np.float16)
        for _, row in df.iterrows()
    }


def main() -> None:
    if not DB_PATH.exists():
        print("No matches.db — run script 08 first.")
        return

    conn = sqlite3.connect(DB_PATH)

    # Load verified matches
    rows = conn.execute(
        """
        SELECT c.market_id, c.article_id, c.article_published_at, c.timestamp_precision,
               v.directional_impact, v.news_type
        FROM verifications v
        JOIN candidates c ON v.market_id=c.market_id AND v.article_id=c.article_id
        WHERE v.is_match=1
        """
    ).fetchall()

    if not rows:
        print("No verified matches found — run script 09 first.")
        conn.close()
        return

    emb_map = _load_embeddings()
    log.info("loaded", verified_pairs=len(rows), embeddings=len(emb_map))

    # Group by market
    market_rows: dict[str, list[dict]] = {}
    for market_id, article_id, pub_at, prec, di, nt in rows:
        market_rows.setdefault(market_id, []).append({
            "market_id": market_id,
            "article_id": article_id,
            "article_published_at": pub_at,
            "timestamp_precision": prec,
            "directional_impact": di,
            "news_type": nt,
            "raw_metadata_json": "{}",
        })

    total_events = 0
    for market_id, verified in market_rows.items():
        events = cluster_market(verified, emb_map)
        for ev in events:
            conn.execute(
                "INSERT OR REPLACE INTO news_events VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ev.event_id, ev.market_id,
                    ev.canonical_ts.isoformat(), ev.timestamp_precision,
                    ev.consensus_directional_impact, ev.dominant_news_type,
                    json.dumps(ev.member_article_ids), ev.member_count,
                    json.dumps(ev.sources),
                ),
            )
        total_events += len(events)

    conn.commit()
    conn.close()

    (MATCHES_DIR / "_EVENTS_SUCCESS").touch()
    print(f"Markets processed: {len(market_rows)}")
    print(f"NewsEvents created: {total_events}")
    if market_rows:
        print(f"Mean events/market: {total_events / len(market_rows):.1f}")


if __name__ == "__main__":
    main()
