"""Script 06: Fetch full article body text — critical path for analysis embeddings.

Usage:
    uv run python scripts/06_fetch_article_bodies.py [--verified-only]

--verified-only: fetch bodies only for articles that have been LLM-verified (faster; run
                 after script 09 if body fetching is lagging). Default fetches the full corpus.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

from src.news.article_fetcher import ArticleFetcher
from src.utils import get_logger

GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")
BODIES_DIR = Path("data/news/bodies")
MATCHES_DB = Path("data/matches/matches.db")

log = get_logger(__name__)


def _load_all_articles() -> pd.DataFrame:
    """Load article metadata (url, article_id) from the corpus."""
    parts = []
    for d in [GDELT_DIR, FEEDS_DIR]:
        if not d.exists():
            continue
        paths = list(d.rglob("*.parquet"))
        if paths:
            parts.append(
                pa.concat_tables([pq.read_table(p) for p in paths]).to_pandas()
            )
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    return df.drop_duplicates(subset=["article_id"])


def _verified_article_ids() -> set[str]:
    """Return set of article_ids that appear in matches.db verifications."""
    if not MATCHES_DB.exists():
        return set()
    conn = sqlite3.connect(MATCHES_DB)
    rows = conn.execute(
        "SELECT DISTINCT article_id FROM verifications WHERE is_match=1"
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def _already_fetched() -> set[str]:
    """Return set of article_ids whose body files already exist on disk."""
    if not BODIES_DIR.exists():
        return set()
    return {p.stem for p in BODIES_DIR.glob("*.txt")}


async def main(verified_only: bool) -> None:
    BODIES_DIR.mkdir(parents=True, exist_ok=True)

    articles_df = _load_all_articles()
    if articles_df.empty:
        print("No articles found — run scripts 04 and 05 first.")
        return

    already_done = _already_fetched()
    todo_df = articles_df[~articles_df["article_id"].isin(already_done)]

    if verified_only:
        verified_ids = _verified_article_ids()
        todo_df = todo_df[todo_df["article_id"].isin(verified_ids)]
        log.info("verified-only mode", verified=len(verified_ids), todo=len(todo_df))
    else:
        log.info("full-corpus mode", todo=len(todo_df))

    if todo_df.empty:
        print("All bodies already fetched.")
        (BODIES_DIR / "_SUCCESS").touch()
        return

    fetcher = ArticleFetcher(max_concurrent=16)
    success = 0
    paywall = 0
    failed = 0

    async def _fetch_one(row: dict) -> None:
        nonlocal success, paywall, failed
        text, ok = await fetcher.fetch_text(row["url"])
        dest = BODIES_DIR / f"{row['article_id']}.txt"
        if ok and text:
            dest.write_text(text, encoding="utf-8")
            success += 1
        else:
            # Write empty sentinel so we don't re-fetch paywalled articles
            dest.write_text("", encoding="utf-8")
            if text is None:
                failed += 1
            else:
                paywall += 1

    tasks = [_fetch_one(row) for row in todo_df[["article_id", "url"]].to_dict("records")]
    # Process in batches to keep memory bounded
    batch_size = 500
    for i in range(0, len(tasks), batch_size):
        await asyncio.gather(*tasks[i:i + batch_size])
        log.info("batch done", done=min(i + batch_size, len(tasks)), total=len(tasks))

    total = success + paywall + failed
    print(f"Fetched:   {success} / {total}  ({100*success/max(total,1):.1f}%)")
    print(f"Paywalled: {paywall}")
    print(f"Failed:    {failed}")

    if total > 0 and success / total >= 0.70:
        (BODIES_DIR / "_SUCCESS").touch()
        print("Body fetch SUCCESS marker written.")
    else:
        print("WARNING: body text coverage below 70% — re-check domain rate limits.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(verified_only=args.verified_only))
