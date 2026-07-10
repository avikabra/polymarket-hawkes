"""Script 09: Verify (market, article) candidate pairs.

Default: rule-based (embedding score + keyword sentiment, no API key needed).
Pass --llm to use Claude Haiku instead (requires ANTHROPIC_API_KEY in .env).

Writes results incrementally to the verifications table (resume-safe),
then writes _VERIFIED_SUCCESS.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from dotenv import load_dotenv

from src.utils import get_logger

load_dotenv()

DB_PATH = Path("data/matches/matches.db")
MATCHES_DIR = Path("data/matches")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")

log = get_logger(__name__)


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Add news_type column if the DB was created before it was added to the schema."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(verifications)")}
    if "news_type" not in cols:
        conn.execute("ALTER TABLE verifications ADD COLUMN news_type TEXT")
        conn.commit()


def _load_article_meta() -> dict[str, dict]:
    """Build article_id → {title, lede} lookup from raw parquet corpus."""
    import pyarrow as pa
    import pyarrow.parquet as pq

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
    meta: dict[str, dict] = {}
    for _, row in df.iterrows():
        meta[row["article_id"]] = {
            "title": str(row.get("title", "")),
            "lede": row.get("lede") or None,
        }
    return meta


def _run_rule_based(conn: sqlite3.Connection, todo: list[tuple], article_meta: dict) -> tuple[int, int]:
    """Verify all pairs with rule-based classifier. Returns (verified, skipped)."""
    from src.matching.rule_verifier import verify_pair_rule

    verified = 0
    skipped = 0
    batch_size = 200

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        rows = []
        now_ts = datetime.now(timezone.utc).isoformat()
        for market_id, article_id, embedding_score in batch:
            meta = article_meta.get(article_id, {})
            result = verify_pair_rule(
                embedding_score=embedding_score,
                article_title=meta.get("title", ""),
                article_lede=meta.get("lede"),
            )
            rows.append((
                market_id, article_id,
                int(result.is_match), result.match_strength,
                result.directional_impact, result.magnitude,
                result.news_type, result.reasoning, now_ts,
            ))
            verified += 1

        conn.executemany(
            "INSERT OR IGNORE INTO verifications "
            "(market_id, article_id, is_match, match_strength, directional_impact, "
            "magnitude, news_type, reasoning, verified_at) VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        log.info("rule verification progress", done=min(i + batch_size, len(todo)), total=len(todo))

    return verified, skipped


async def _run_llm(conn: sqlite3.Connection, todo: list[tuple], article_meta: dict, market_questions: dict) -> tuple[int, int]:
    """Verify all pairs with Claude Haiku. Returns (verified, skipped)."""
    from anthropic import AsyncAnthropic
    from src.matching.llm_verifier import verify_pair

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set in .env — cannot use --llm mode.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)
    batch_size = 50
    verified = 0
    skipped = 0

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        tasks = []
        for market_id, article_id, _score in batch:
            question = market_questions.get(market_id, "")
            meta = article_meta.get(article_id, {})
            tasks.append(verify_pair(
                client=client,
                market_id=market_id,
                market_question=question,
                article_id=article_id,
                article_title=meta.get("title", ""),
                article_lede=meta.get("lede"),
            ))

        results = await asyncio.gather(*tasks)
        now_ts = datetime.now(timezone.utc).isoformat()

        rows = []
        for (market_id, article_id, _score), result in zip(batch, results):
            if result is None:
                skipped += 1
                continue
            rows.append((
                market_id, article_id,
                int(result.is_match), result.match_strength,
                result.directional_impact, result.magnitude,
                result.news_type, result.reasoning, now_ts,
            ))
            verified += 1

        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO verifications "
                "(market_id, article_id, is_match, match_strength, directional_impact, "
                "magnitude, news_type, reasoning, verified_at) VALUES (?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()

        log.info("LLM verification progress", done=min(i + batch_size, len(todo)), total=len(todo))

    return verified, skipped


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true", help="Use Claude Haiku (requires ANTHROPIC_API_KEY)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print("No matches.db found — run script 08 first.")
        return

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    market_questions: dict[str, str] = dict(
        zip(universe_df["market_id"].astype(str), universe_df["question"].astype(str))
    )

    article_meta = _load_article_meta()

    conn = sqlite3.connect(DB_PATH)
    _migrate_db(conn)

    verified_pairs = set(
        conn.execute("SELECT market_id, article_id FROM verifications").fetchall()
    )
    # Include embedding_score so rule-based path can use it directly
    candidates = conn.execute(
        "SELECT market_id, article_id, embedding_score FROM candidates"
    ).fetchall()
    todo = [(m, a, s) for m, a, s in candidates if (m, a) not in verified_pairs]
    log.info("candidates to verify", total=len(candidates), remaining=len(todo))

    if args.llm:
        log.info("using LLM verifier (Claude Haiku)")
        verified, skipped = await _run_llm(conn, todo, article_meta, market_questions)
    else:
        log.info("using rule-based verifier")
        verified, skipped = _run_rule_based(conn, todo, article_meta)

    conn.close()
    MATCHES_DIR.mkdir(parents=True, exist_ok=True)
    (MATCHES_DIR / "_VERIFIED_SUCCESS").touch()

    print(f"Verified:  {verified}")
    print(f"Skipped:   {skipped}")
    print("Run script 10 (dedup) next.")


if __name__ == "__main__":
    asyncio.run(main())
