"""Gamma API client for the contract pull (series, events, tags).

Thin, cached, rate-limited. All classification lives in src/ingest/polymarket_contracts.py,
never here. Paging convention: request `limit`, advance `offset`, stop on a short page.
"""
import json
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.utils import DiskCache, TokenBucket, get_logger

_BASE = "https://gamma-api.polymarket.com"


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {429, 500, 502, 503, 504}


class GammaClient:
    def __init__(self, cache_dir: str = "data/.cache/gamma", requests_per_second: float = 4.0) -> None:
        self._cache = DiskCache(cache_dir)
        self._bucket = TokenBucket(rate=requests_per_second, capacity=requests_per_second)
        self._log = get_logger(__name__)

    @retry(
        retry=retry_if_exception(_is_transient),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(8),
        reraise=True,
    )
    async def _fetch(self, path: str, params: dict) -> Any:
        await self._bucket.acquire()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(_BASE + path, params=params)
            resp.raise_for_status()
            return resp.json()

    async def get(self, path: str, params: dict | None = None) -> Any:
        params = params or {}
        key = "gamma2:" + path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        cached = self._cache.get(key)
        if cached is not None:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass  # corrupt entry from an interrupted write; re-fetch
        data = await self._fetch(path, params)
        self._cache.set(key, json.dumps(data).encode())
        return data

    async def pages(self, path: str, limit: int, **params: Any) -> list[dict]:
        """Every row of a paged list endpoint, until a short page comes back."""
        rows: list[dict] = []
        offset = 0
        while True:
            page = await self.get(path, {**params, "limit": limit, "offset": offset})
            rows.extend(page)
            if len(page) < limit:
                return rows
            offset += limit

    async def all_series(self) -> list[dict]:
        """/series, 50 per page. The embedded `events` list (capped ~20) is dropped."""
        rows = await self.pages("/series", 50)
        for r in rows:
            r.pop("events", None)
        return rows

    async def series_events(self, series_id: str) -> list[dict]:
        """Every event of a series via /events?series_id= (100 per page)."""
        return await self.pages("/events", 100, series_id=series_id)

    async def tag_events(self, tag_id: str, end_date_max: str, end_date_min: str | None = None) -> list[dict]:
        """Closed events carrying `tag_id`, ending before `end_date_max` (and after `end_date_min`)."""
        params = {"tag_id": tag_id, "closed": "true", "end_date_max": end_date_max}
        if end_date_min:
            params["end_date_min"] = end_date_min
        return await self.pages("/events", 100, **params)

    async def all_tags(self) -> list[dict]:
        return await self.pages("/tags", 100)
