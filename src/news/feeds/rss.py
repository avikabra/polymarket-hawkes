import asyncio
import hashlib
import json
from datetime import datetime, timezone

import feedparser
import httpx

from src.schemas import Article
from src.utils import DiskCache, get_logger

# Some publishers (CNBC, Yahoo Finance) block the default python-httpx UA
# with 403/429; a realistic browser UA is enough to get a normal response.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}


class RSSFetcher:
    # RSS feeds are live tickers, not stable archives; an hour bounds how
    # stale a cached response can be without re-fetching on every run.
    _CACHE_TTL_SECONDS = 3600

    def __init__(self, cache_dir: str = "data/.cache/rss") -> None:
        self._cache = DiskCache(cache_dir)
        self._log = get_logger(__name__)

    def _parse_published(self, entry) -> tuple[datetime | None, str]:
        pt = entry.get("published_parsed")
        if pt is None:
            return None, "day"
        return datetime(*pt[:6], tzinfo=timezone.utc), "minute"

    async def fetch(self, url: str, source_name: str) -> list[Article]:
        cache_key = f"rss:{url}"
        cached = self._cache.get(cache_key, max_age_seconds=self._CACHE_TTL_SECONDS)

        if cached is not None:
            content = cached.decode()
        else:
            async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                content = resp.text
                self._cache.set(cache_key, content.encode())

        feed = feedparser.parse(content)
        articles = []
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link:
                continue

            article_id = hashlib.sha256(link.encode()).hexdigest()
            published_at, precision = self._parse_published(entry)

            summary = entry.get("summary", "") or ""
            lede_words = summary.split()[:150]
            lede = " ".join(lede_words) if lede_words else None

            raw_metadata = {
                "feed_url": url,
                "entry_id": entry.get("id", ""),
                "tags": [t.get("term", "") for t in entry.get("tags", [])],
            }

            articles.append(Article(
                article_id=article_id,
                source=source_name,
                url=link,
                published_at=published_at,
                timestamp_precision=precision,
                title=entry.get("title", link),
                lede=lede,
                body_text=None,
                body_text_available=False,
                entities=[],
                themes=[],
                raw_metadata_json=json.dumps(raw_metadata),
            ))

        self._log.info("rss fetch done", extra={"url": url, "count": len(articles)})
        return articles

    async def fetch_all(self, feed_list: list[dict]) -> list[Article]:
        sem = asyncio.Semaphore(5)

        async def _fetch_one(feed: dict) -> list[Article]:
            async with sem:
                try:
                    return await self.fetch(feed["url"], feed["name"])
                except Exception as exc:
                    self._log.warning(
                        "rss fetch failed",
                        extra={"url": feed["url"], "error": str(exc)},
                    )
                    return []

        results = await asyncio.gather(*[_fetch_one(f) for f in feed_list])
        return [a for batch in results for a in batch]
