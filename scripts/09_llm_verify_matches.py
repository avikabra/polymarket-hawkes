"""Script 09: LLM-verify (market, article) candidate pairs via Claude Haiku.

Reads candidates from matches.db, calls src/matching/llm_verifier.py,
writes results incrementally to the verifications table (resume-safe),
then writes _VERIFIED_SUCCESS.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from src.matching.llm_verifier import verify_pair
from src.utils import get_logger

load_dotenv()

DB_PATH = Path("data/matches/matches.db")
MATCHES_DIR = Path("data/matches")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")

log = get_logger(__name__)

# Columns needed from the universe to get market question
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")


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


async def main() -> None:
    if not DB_PATH.exists():
        print("No matches.db found — run script 08 first.")
        return

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set in .env — cannot run LLM verification.")
        return

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    market_questions: dict[str, str] = dict(
        zip(universe_df["market_id"].astype(str), universe_df["question"].astype(str))
    )

    article_meta = _load_article_meta()

    conn = sqlite3.connect(DB_PATH)

    # Load unverified candidates
    verified_pairs = set(
        conn.execute("SELECT market_id, article_id FROM verifications").fetchall()
    )
    candidates = conn.execute(
        "SELECT market_id, article_id FROM candidates"
    ).fetchall()
    todo = [(m, a) for m, a in candidates if (m, a) not in verified_pairs]
    log.info("candidates to verify", total=len(candidates), remaining=len(todo))

    client = AsyncAnthropic(api_key=api_key)

    batch_size = 50  # write to DB after each batch
    verified = 0
    skipped = 0

    for i in range(0, len(todo), batch_size):
        batch = todo[i:i + batch_size]
        tasks = []
        for market_id, article_id in batch:
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
        for (market_id, article_id), result in zip(batch, results):
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
                "INSERT OR IGNORE INTO verifications VALUES (?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()

        done = min(i + batch_size, len(todo))
        log.info("verification progress", done=done, total=len(todo))

    conn.close()
    MATCHES_DIR.mkdir(parents=True, exist_ok=True)
    (MATCHES_DIR / "_VERIFIED_SUCCESS").touch()

    matched = sum(1 for m, a in todo if True)  # recount from DB
    print(f"Verified:  {verified}")
    print(f"Skipped:   {skipped}")
    print("Run script 10 (dedup) next.")


if __name__ == "__main__":
    asyncio.run(main())
