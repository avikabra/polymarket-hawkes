"""Script 05: Pull category-specific feeds (ESPN, RSS, NBA Stats)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from collections import defaultdict

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.news.feeds.espn import ESPNFetcher
from src.news.feeds.nba_stats import NBAStatsFetcher
from src.news.feeds.rss import RSSFetcher
from src.schemas import Article
from src.utils import get_logger

log = get_logger(__name__)


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _date_to_season(start_date: str) -> str:
    """Convert YYYY-MM-DD start date to NBA season string like '2024-25'."""
    year = int(start_date[:4])
    return f"{year}-{str(year + 1)[2:]}"


def _deduplicate(articles: list[Article]) -> list[Article]:
    seen: dict[str, Article] = {}
    for a in articles:
        if a.article_id not in seen:
            seen[a.article_id] = a
    return list(seen.values())


async def _pull_category(
    cat: str,
    cat_cfg: dict,
    start_date: str,
    end_date: str,
) -> list[Article]:
    articles: list[Article] = []

    espn_sport = cat_cfg.get("feeds", {}).get("espn_sport")
    if espn_sport:
        try:
            espn_articles = await ESPNFetcher().fetch_news(espn_sport, start_date, end_date)
            articles.extend(espn_articles)
            log.info("espn done", extra={"cat": cat, "count": len(espn_articles)})
        except Exception as exc:
            print(f"WARNING: ESPN fetch failed for {cat}: {exc}")

    if cat_cfg.get("feeds", {}).get("nba_stats"):
        try:
            season = _date_to_season(start_date)
            nba_articles = await NBAStatsFetcher().fetch_game_events(season)
            articles.extend(nba_articles)
            log.info("nba_stats done", extra={"cat": cat, "count": len(nba_articles)})
        except Exception as exc:
            print(f"WARNING: NBA Stats fetch failed for {cat}: {exc}")

    rss_feeds = cat_cfg.get("feeds", {}).get("rss", [])
    if rss_feeds:
        try:
            rss_articles = await RSSFetcher().fetch_all(rss_feeds)
            articles.extend(rss_articles)
            log.info("rss done", extra={"cat": cat, "count": len(rss_articles)})
        except Exception as exc:
            print(f"WARNING: RSS fetch failed for {cat}: {exc}")

    return articles


async def main() -> None:
    focal = _load_yaml("config/focal.yaml")["focal"]
    categories_cfg = _load_yaml("config/categories.yaml")["categories"]

    start_date = focal["start_date"]
    end_date = focal["end_date"]
    focal_cats: list[str] = focal["categories"]

    all_articles: list[Article] = []
    for cat in focal_cats:
        cat_cfg = categories_cfg.get(cat, {})
        cat_articles = await _pull_category(cat, cat_cfg, start_date, end_date)
        print(f"  {cat}: {len(cat_articles)} articles fetched")
        all_articles.extend(cat_articles)

    all_articles = _deduplicate(all_articles)

    # Partition by source + year + month from published_at
    out_root = Path("data/news/feeds")
    groups: dict[tuple, list] = defaultdict(list)
    for a in all_articles:
        if a.published_at:
            key = (a.source, a.published_at.year, a.published_at.month)
        else:
            key = (a.source, 0, 0)
        groups[key].append(a.model_dump())

    for (source, year, month), records in groups.items():
        if year == 0:
            out_path = out_root / f"source={source}/year=unknown/month=unknown/part-0.parquet"
        else:
            out_path = out_root / f"source={source}/year={year}/month={month:02d}/part-0.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(pd.DataFrame(records)), out_path)

    total = len(all_articles)
    sources: dict[str, list[Article]] = defaultdict(list)
    for a in all_articles:
        sources[a.source].append(a)

    print(f"\nTotal articles (after dedup): {total}")
    for source, src_articles in sorted(sources.items()):
        n = len(src_articles)
        minute_pct = sum(1 for a in src_articles if a.timestamp_precision == "minute") / n * 100
        day_pct = sum(1 for a in src_articles if a.timestamp_precision == "day") / n * 100
        print(f"  {source}: {n} articles | minute={minute_pct:.0f}% day={day_pct:.0f}%")

    if total:
        overall_minute = sum(1 for a in all_articles if a.timestamp_precision == "minute") / total * 100
        overall_day = sum(1 for a in all_articles if a.timestamp_precision == "day") / total * 100
        print(f"\nOverall: minute={overall_minute:.0f}% | day={overall_day:.0f}%")

    success = out_root / "_SUCCESS"
    out_root.mkdir(parents=True, exist_ok=True)
    success.touch()
    log.info("done", extra={"total": total})


if __name__ == "__main__":
    asyncio.run(main())
