import hashlib
import json
from datetime import datetime, timezone

import httpx

from src.schemas import Article
from src.utils import DiskCache, TokenBucket, get_logger

_BASE = "https://site.api.espn.com/apis/site/v2/sports"


class ESPNFetcher:
    def __init__(self, cache_dir: str = "data/.cache/espn") -> None:
        self._cache = DiskCache(cache_dir)
        self._rate = TokenBucket(rate=1.0, capacity=1.0)
        self._log = get_logger(__name__)

    def _parse_dt(self, s: str) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def _get_page(self, client: httpx.AsyncClient, url: str, params: dict) -> dict:
        cache_key = f"espn:{url}:{json.dumps(params, sort_keys=True)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)
        await self._rate.acquire()
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        self._cache.set(cache_key, resp.content)
        return resp.json()

    async def fetch_news(self, sport: str, start_date: str, end_date: str) -> list[Article]:
        """Fetch ESPN news for a sport within a date window (YYYY-MM-DD inclusive)."""
        url = f"{_BASE}/{sport}/news"
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)

        articles: list[Article] = []
        seen_ids: set[str] = set()
        done = False
        page = 1
        page_count = 1

        async with httpx.AsyncClient(timeout=30) as client:
            while page <= page_count and not done:
                data = await self._get_page(client, url, {"limit": 100, "page": page})
                page_count = data.get("pageCount", 1)

                for item in data.get("articles", []):
                    pub_dt = self._parse_dt(item.get("published", ""))

                    # ESPN returns newest-first; once we pass start_dt no more relevant articles follow
                    if pub_dt and pub_dt < start_dt:
                        done = True
                        break

                    if pub_dt and pub_dt > end_dt:
                        continue

                    link = (item.get("links", {}).get("web", {}) or {}).get("href", "")
                    if not link:
                        continue

                    article_id = hashlib.sha256(link.encode()).hexdigest()
                    if article_id in seen_ids:
                        continue
                    seen_ids.add(article_id)

                    raw_metadata = {
                        "espn_id": str(item.get("id", "")),
                        "sport": sport,
                        "categories": [
                            c.get("description", "") for c in item.get("categories", [])
                        ],
                    }

                    articles.append(Article(
                        article_id=article_id,
                        source="espn",
                        url=link,
                        published_at=pub_dt,
                        timestamp_precision="minute",
                        title=item.get("headline", link),
                        lede=item.get("description") or None,
                        body_text=None,
                        text_available=False,
                        entities=[],
                        themes=[],
                        raw_metadata_json=json.dumps(raw_metadata),
                    ))

                page += 1

        self._log.info("espn fetch done", extra={"sport": sport, "count": len(articles)})
        return articles
