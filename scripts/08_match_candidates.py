"""Script 08: Per-group top-K candidate article retrieval into matches.db (D4 schema v2).

Group-keyed (628 contract_groups.parquet rows), not market-keyed (6,928 universe.parquet
rows) — an ~11x reduction in FAISS searches. A group's window is the union of its member
markets' [created_at, end_at + 24h] windows, since contract_groups.parquet doesn't carry
dates itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from tqdm import tqdm

from src.matching.candidate_finder import CandidateFinder
from src.news.normalizer import build_matching_text_corpus
from src.utils import assert_covers, get_logger

# Paths — keep in sync with config/paths.yaml
EMBEDDINGS_DIR = Path("data/news/matching_embeddings")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
CONTRACT_GROUPS_PATH = Path("data/polymarket/contract_groups.parquet")
MATCHES_DIR = Path("data/matches")
DB_PATH = MATCHES_DIR / "matches.db"

FAISS_INDEX_PATH = EMBEDDINGS_DIR / "articles.faiss"
ARTICLE_ID_IDX_PATH = EMBEDDINGS_DIR / "article_id_index.parquet"
GROUP_EMB_PATH = EMBEDDINGS_DIR / "group_embeddings.parquet"

GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")

_META_COLS = ["article_id", "published_at", "timestamp_precision", "raw_metadata_json"]

log = get_logger(__name__)

# Schema v2 (group-keyed). matches.db is fresh — A0 moved the stale market-keyed
# May-2026 db aside — so plain CREATE TABLE IF NOT EXISTS is safe (no migration).
_DDL = [
    """
    CREATE TABLE IF NOT EXISTS candidates (
      group_id TEXT, article_id TEXT, embedding_score REAL,
      article_published_at TEXT, timestamp_precision TEXT,
      PRIMARY KEY (group_id, article_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verifications (
      group_id TEXT, article_id TEXT, is_match INTEGER,
      match_strength REAL, directional_impact INTEGER, magnitude REAL,
      news_type TEXT, reasoning TEXT, review_status TEXT, verified_at TEXT,
      PRIMARY KEY (group_id, article_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news_events (
      event_id TEXT PRIMARY KEY, group_id TEXT,
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


def _build_meta_path() -> str:
    meta_cache = MATCHES_DIR / "article_meta.parquet"
    if meta_cache.exists():
        return str(meta_cache)

    df = build_matching_text_corpus(str(GDELT_DIR), str(FEEDS_DIR))

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


def _group_windows(
    contract_groups_df: pd.DataFrame, universe_df: pd.DataFrame
) -> dict[str, tuple[datetime, datetime]]:
    """group_id -> (window_start, window_end), unioned over member markets.

    contract_groups.parquet carries no dates of its own — each group's window is
    [min(member created_at), max(member end_at) + 24h] via a join against universe_df.
    """
    mkt_dates = universe_df.set_index("market_id")[["created_at", "end_at"]]
    windows: dict[str, tuple[datetime, datetime]] = {}
    for _, group in contract_groups_df.iterrows():
        member_ids = list(group["member_market_ids"])
        sub = mkt_dates.reindex(member_ids).dropna()
        if sub.empty:
            continue
        window_start = pd.Timestamp(sub["created_at"].min()).to_pydatetime()
        window_end = pd.Timestamp(sub["end_at"].max()).to_pydatetime() + timedelta(hours=24)
        windows[str(group["group_id"])] = (window_start, window_end)
    return windows


def main() -> None:
    MATCHES_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)

    for prereq, label in [
        (UNIVERSE_PATH, "universe.parquet"),
        (CONTRACT_GROUPS_PATH, "contract_groups.parquet"),
        (GROUP_EMB_PATH, "group_embeddings.parquet"),
        (FAISS_INDEX_PATH, "articles.faiss"),
        (ARTICLE_ID_IDX_PATH, "article_id_index.parquet"),
    ]:
        if not prereq.exists():
            print(f"Missing prerequisite: {prereq} — run scripts 01–07 first.")
            conn.close()
            return

    top_k = _load_top_k()
    universe_df = pd.read_parquet(UNIVERSE_PATH)
    contract_groups_df = pd.read_parquet(CONTRACT_GROUPS_PATH)
    assert_covers(
        [GDELT_DIR, FEEDS_DIR],
        (cid for cid in universe_df["company_id"] if cid),
        (
            pd.Timestamp(universe_df["created_at"].min()).isoformat(),
            pd.Timestamp(universe_df["end_at"].max()).isoformat(),
        ),
    )
    group_emb_df = pd.read_parquet(GROUP_EMB_PATH)
    group_emb_map: dict[str, np.ndarray] = {
        row["group_id"]: np.frombuffer(row["embedding"], dtype=np.float16)
        for _, row in group_emb_df.iterrows()
    }
    group_windows = _group_windows(contract_groups_df, universe_df)

    finder = CandidateFinder(
        faiss_index_path=str(FAISS_INDEX_PATH),
        article_id_index_path=str(ARTICLE_ID_IDX_PATH),
        article_meta_path=_build_meta_path(),
        k=top_k,
    )

    total_candidates = 0
    groups_processed = 0

    for _, group in tqdm(contract_groups_df.iterrows(), total=len(contract_groups_df), desc="groups"):
        gid = str(group["group_id"])

        if conn.execute("SELECT 1 FROM candidates WHERE group_id=? LIMIT 1", (gid,)).fetchone():
            continue

        emb = group_emb_map.get(gid)
        if emb is None:
            continue

        window = group_windows.get(gid)
        if window is None:
            continue
        window_start, window_end = window

        # CandidateFinder is market/group-agnostic — it just echoes back whatever
        # id it's called with under the dict key "market_id"; here that id is gid.
        candidates = finder.find_candidates(gid, emb, window_start, window_end)

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
        groups_processed += 1

    conn.close()
    (MATCHES_DIR / "_CANDIDATES_SUCCESS").touch()

    print(f"Groups processed:      {groups_processed}")
    print(f"Total candidates:      {total_candidates}")
    if groups_processed:
        print(f"Mean candidates/group: {total_candidates / groups_processed:.1f}")


if __name__ == "__main__":
    main()
