"""Script 08: Per-market top-K candidate article retrieval into matches.db (D4 schema)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from datetime import timedelta

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from tqdm import tqdm

from src.matching.candidate_finder import CandidateFinder
from src.utils import get_logger

# Paths — keep in sync with config/paths.yaml
EMBEDDINGS_DIR = Path("data/news/matching_embeddings")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
MATCHES_DIR = Path("data/matches")
DB_PATH = MATCHES_DIR / "matches.db"

FAISS_INDEX_PATH = EMBEDDINGS_DIR / "articles.faiss"
ARTICLE_ID_IDX_PATH = EMBEDDINGS_DIR / "article_id_index.parquet"
MARKET_EMB_PATH = EMBEDDINGS_DIR / "market_embeddings.parquet"

GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")

_META_COLS = ["article_id", "published_at", "timestamp_precision", "raw_metadata_json"]

log = get_logger(__name__)

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS candidates (
      market_id TEXT, article_id TEXT, embedding_score REAL,
      article_published_at TEXT, timestamp_precision TEXT,
      PRIMARY KEY (market_id, article_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verifications (
      market_id TEXT, article_id TEXT, is_match INTEGER,
      match_strength REAL, directional_impact INTEGER, magnitude REAL,
      news_type TEXT, reasoning TEXT, verified_at TEXT,
      PRIMARY KEY (market_id, article_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_events (
      event_id TEXT PRIMARY KEY, market_id TEXT,
      canonical_ts TEXT, timestamp_precision TEXT,
      consensus_directional_impact INTEGER, dominant_news_type TEXT,
      member_article_ids TEXT, member_count INTEGER, sources TEXT
    )
    """,
]


def _init_db(conn: sqlite3.Connection) -> None:
    for ddl in _DDL:
        conn.execute(ddl)
    conn.commit()


def _load_parquet_dir(d: Path) -> pd.DataFrame:
    paths = list(d.rglob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    return pa.concat_tables([pq.read_table(p) for p in paths]).to_pandas()


def _build_meta_path() -> str:
    meta_cache = MATCHES_DIR / "article_meta.parquet"
    if meta_cache.exists():
        return str(meta_cache)

    parts = [_load_parquet_dir(d) for d in [GDELT_DIR, FEEDS_DIR] if d.exists()]
    parts = [p for p in parts if not p.empty]
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    if df.empty:
        df = pd.DataFrame(columns=_META_COLS)
    else:
        keep = [c for c in _META_COLS if c in df.columns]
        df = df[keep]

    pq.write_table(pa.Table.from_pandas(df), meta_cache)
    log.info("article metadata cached", rows=len(df))
    return str(meta_cache)


def _load_top_k() -> int:
    cfg_path = Path("config/analysis.yaml")
    if cfg_path.exists():
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        return int(cfg.get("matching", {}).get("top_k", 150))
    return 150


def main() -> None:
    MATCHES_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)

    for prereq, label in [
        (UNIVERSE_PATH, "universe.parquet"),
        (MARKET_EMB_PATH, "market_embeddings.parquet"),
        (FAISS_INDEX_PATH, "articles.faiss"),
        (ARTICLE_ID_IDX_PATH, "article_id_index.parquet"),
    ]:
        if not prereq.exists():
            print(f"Missing prerequisite: {prereq} — run scripts 01–07 first.")
            conn.close()
            return

    top_k = _load_top_k()
    universe_df = pd.read_parquet(UNIVERSE_PATH)
    market_emb_df = pd.read_parquet(MARKET_EMB_PATH)
    market_emb_map: dict[str, np.ndarray] = {
        row["market_id"]: np.frombuffer(row["embedding"], dtype=np.float16)
        for _, row in market_emb_df.iterrows()
    }

    finder = CandidateFinder(
        faiss_index_path=str(FAISS_INDEX_PATH),
        article_id_index_path=str(ARTICLE_ID_IDX_PATH),
        article_meta_path=_build_meta_path(),
        k=top_k,
    )

    total_candidates = 0
    markets_processed = 0

    for _, market in tqdm(universe_df.iterrows(), total=len(universe_df), desc="markets"):
        mid = str(market["market_id"])

        if conn.execute("SELECT 1 FROM candidates WHERE market_id=? LIMIT 1", (mid,)).fetchone():
            continue

        emb = market_emb_map.get(mid)
        if emb is None:
            continue

        window_start = pd.Timestamp(market["created_at"]).to_pydatetime()
        window_end = pd.Timestamp(market["end_at"]).to_pydatetime() + timedelta(hours=24)

        candidates = finder.find_candidates(mid, emb, window_start, window_end)

        if candidates:
            conn.executemany(
                "INSERT OR IGNORE INTO candidates VALUES (?,?,?,?,?)",
                [
                    (c["market_id"], c["article_id"], c["embedding_score"],
                     c["article_published_at"], c["timestamp_precision"])
                    for c in candidates
                ],
            )
        conn.commit()

        total_candidates += len(candidates)
        markets_processed += 1

    conn.close()
    (MATCHES_DIR / "_CANDIDATES_SUCCESS").touch()

    print(f"Markets processed:    {markets_processed}")
    print(f"Total candidates:     {total_candidates}")
    if markets_processed:
        print(f"Mean candidates/mkt: {total_candidates / markets_processed:.1f}")


if __name__ == "__main__":
    main()
