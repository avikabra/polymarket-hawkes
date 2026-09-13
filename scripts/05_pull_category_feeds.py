"""Script 05: Pull category-specific RSS feeds (general business/markets wires)."""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import defaultdict

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.news.feeds.rss import RSSFetcher
from src.schemas import Article
from src.utils import get_logger, write_scope

log = get_logger(__name__)

UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
OUT_ROOT = Path("data/news/feeds")
STALE_THRESHOLD_HOURS = 24  # a live news wire should have something newer than this


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _deduplicate(articles: list[Article]) -> list[Article]:
    seen: dict[str, Article] = {}
    for a in articles:
        if a.article_id not in seen:
            seen[a.article_id] = a
    return list(seen.values())


async def _pull_category(cat: str, cat_cfg: dict) -> list[Article]:
    rss_feeds = cat_cfg.get("feeds", {}).get("rss", [])
    if not rss_feeds:
        return []
    try:
        articles = await RSSFetcher().fetch_all(rss_feeds)
        log.info("rss done", extra={"cat": cat, "count": len(articles)})
        return articles
    except Exception as exc:
        print(f"WARNING: RSS fetch failed for {cat}: {exc}")
        return []


async def main() -> None:
    focal = _load_yaml("config/focal.yaml")["focal"]
    categories_cfg = _load_yaml("config/categories.yaml")["categories"]

    # Company-universe discovery window (script 01), not the legacy sports
    # start_date/end_date which stays scoped to scripts 02-04.
    start_date = focal["discovery_start_date"]
    end_date = focal["discovery_end_date"]

    all_articles: list[Article] = []
    for cat, cat_cfg in categories_cfg.items():
        cat_articles = await _pull_category(cat, cat_cfg)
        print(f"  {cat}: {len(cat_articles)} articles fetched")
        all_articles.extend(cat_articles)

    all_articles = _deduplicate(all_articles)

    # Partition by source + year + month from published_at
    groups: dict[tuple, list] = defaultdict(list)
    for a in all_articles:
        if a.published_at:
            key = (a.source, a.published_at.year, a.published_at.month)
        else:
            key = (a.source, 0, 0)
        groups[key].append(a.model_dump())

    for (source, year, month), records in groups.items():
        if year == 0:
            out_path = OUT_ROOT / f"source={source}/year=unknown/month=unknown/part-0.parquet"
        else:
            out_path = OUT_ROOT / f"source={source}/year={year}/month={month:02d}/part-0.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(pd.DataFrame(records)), out_path)

    total = len(all_articles)
    sources: dict[str, list[Article]] = defaultdict(list)
    for a in all_articles:
        sources[a.source].append(a)

    print(f"\nTotal articles (after dedup): {total}")
    now = datetime.now(timezone.utc)
    for source, src_articles in sorted(sources.items()):
        n = len(src_articles)
        minute_pct = sum(1 for a in src_articles if a.timestamp_precision == "minute") / n * 100
        day_pct = sum(1 for a in src_articles if a.timestamp_precision == "day") / n * 100
        dated = [a.published_at for a in src_articles if a.published_at]
        if dated:
            newest, oldest = max(dated), min(dated)
            age_hours = (now - newest).total_seconds() / 3600
            staleness = f"newest={newest.date()} oldest={oldest.date()}"
            if age_hours > STALE_THRESHOLD_HOURS:
                staleness += f" WARNING: newest item is {age_hours:.0f}h old (stale feed?)"
        else:
            staleness = "no dated items"
        print(f"  {source}: {n} articles | minute={minute_pct:.0f}% day={day_pct:.0f}% | {staleness}")

    if total:
        overall_minute = sum(1 for a in all_articles if a.timestamp_precision == "minute") / total * 100
        overall_day = sum(1 for a in all_articles if a.timestamp_precision == "day") / total * 100
        print(f"\nOverall: minute={overall_minute:.0f}% | day={overall_day:.0f}%")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "_SUCCESS").touch()

    # Scope sidecar: these are general business wires, not per-company feeds
    # (no per-company RSS exists for the universe), so "coverage" is recorded
    # as intent — the whole universe, same as the feeds are meant to serve —
    # rather than a crude keyword match against article text, which would be
    # both unreliable (ticker collisions with common words) and redundant
    # with the real entity matching done downstream in scripts 07-09. Only
    # written when the pull actually produced articles, so a fully-broken
    # pull (e.g. all feeds down) fails the downstream coverage guard loudly
    # instead of trivially passing.
    if total:
        universe_df = pd.read_parquet(UNIVERSE_PATH)
        write_scope(
            OUT_ROOT,
            (cid for cid in universe_df["company_id"] if cid),
            (start_date, end_date),
        )

    log.info("done", extra={"total": total})


if __name__ == "__main__":
    asyncio.run(main())
