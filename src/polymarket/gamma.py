import asyncio
import json as _json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.utils import DiskCache, TokenBucket, get_logger

_BASE = "https://gamma-api.polymarket.com"


def _is_429(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


def _extract_tags(raw_tags: Any) -> list[str]:
    if not raw_tags:
        return []
    if isinstance(raw_tags[0], str):
        return raw_tags
    return [t.get("slug") or t.get("label", "") for t in raw_tags]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GammaClient:
    def __init__(self, cache_dir: str = "data/.cache/gamma") -> None:
        self._cache = DiskCache(cache_dir)
        self._bucket = TokenBucket(rate=1.0, capacity=60)
        self._log = get_logger(__name__)

    @retry(
        retry=retry_if_exception(_is_429),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _get(self, path: str, params: dict) -> Any:
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        cached = self._cache.get(key)
        if cached is not None:
            try:
                return _json.loads(cached)
            except _json.JSONDecodeError:
                # Corrupt/truncated cache entry (e.g. partial write on ENOSPC);
                # fall through to re-fetch rather than crash the enumeration.
                pass

        await self._bucket.acquire()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(_BASE + path, params=params)
            resp.raise_for_status()

        data = resp.json()
        self._cache.set(key, _json.dumps(data).encode())
        return data

    async def _resolve_tag_id(self, tag: str) -> str | None:
        try:
            data = await self._get(f"/tags/slug/{tag}", {})
        except httpx.HTTPStatusError as exc:
            self._log.warning("tag not found", extra={"tag": tag, "status": exc.response.status_code})
            return None
        return str(data.get("id")) if data.get("id") is not None else None

    async def list_markets(
        self,
        tag: str,
        closed: bool = True,
        start_after: str | None = None,
        end_before: str | None = None,
    ) -> list[dict]:
        # The Gamma /markets endpoint silently ignores the `tag` param (every tag
        # returns the same unfiltered page) and never populates a `tags` field.
        # We instead query /events with the numeric `tag_id`, which filters
        # correctly and carries tags; each event's markets inherit its tags.
        tag_id = await self._resolve_tag_id(tag)
        if tag_id is None:
            return []

        results: list[dict] = []
        offset, limit = 0, 100
        while True:
            params: dict = {
                "closed": str(closed).lower(),
                "tag_id": tag_id,
                "limit": limit,
                "offset": offset,
            }
            if start_after:
                params["end_date_min"] = start_after
            if end_before:
                params["end_date_max"] = end_before
            try:
                page = await self._get("/events", params)
            except httpx.HTTPStatusError as exc:
                # API returns 422 when offset exceeds available results — treat as end
                self._log.warning(
                    "pagination stopped",
                    extra={"tag": tag, "offset": offset, "status": exc.response.status_code},
                )
                break
            if not page:
                break
            for event in page:
                event_tags = event.get("tags") or []
                for mkt in event.get("markets") or []:
                    mkt = dict(mkt)
                    mkt["tags"] = event_tags  # markets inherit parent-event tags
                    results.append(mkt)
            if len(page) < limit:
                break
            offset += limit
        return results

    async def enumerate_markets(
        self,
        start: datetime,
        end: datetime,
        *,
        page_limit: int = 100,
        inter_page_sleep: float = 0.25,
        inter_day_sleep: float = 1.0,
    ) -> AsyncIterator[dict]:
        """Yield raw market dicts for all markets whose endDate falls in [start, end).

        Uses day-level slicing to stay under the ~2,100-offset ceiling.
        Results are deduplicated within a day by conditionId; cross-day
        deduplication is the caller's responsibility (use a seen-set on conditionId).
        """
        cur = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while cur < end:
            next_day = cur + timedelta(days=1)
            ds = cur.strftime("%Y-%m-%dT%H:%M:%SZ")
            de = next_day.strftime("%Y-%m-%dT%H:%M:%SZ")

            seen_today: set[str] = set()

            for closed_val in ("true", "false"):
                offset = 0
                while True:
                    params: dict = {
                        "limit": page_limit,
                        "offset": offset,
                        "end_date_min": ds,
                        "end_date_max": de,
                        "closed": closed_val,
                    }
                    try:
                        page = await self._get("/markets", params)
                    except httpx.HTTPStatusError as exc:
                        # 422 = past offset ceiling; treat as end-of-results
                        self._log.warning(
                            "enumerate_markets pagination stopped",
                            extra={"day": ds, "closed": closed_val, "offset": offset, "status": exc.response.status_code},
                        )
                        break
                    if not page:
                        break
                    for mkt in page:
                        cid = mkt.get("conditionId") or mkt.get("id") or ""
                        if cid and cid not in seen_today:
                            seen_today.add(cid)
                            yield mkt
                    if len(page) < page_limit:
                        break
                    offset += page_limit
                    await asyncio.sleep(inter_page_sleep)

            cur = next_day
            await asyncio.sleep(inter_day_sleep)

    async def get_market(self, condition_id: str) -> dict:
        return await self._get(f"/markets/{condition_id}", {})

    def parse_market(
        self,
        raw: dict,
        category: str = "",
        *,
        classification: dict | None = None,
        strike_fields: dict | None = None,
    ) -> Any:
        from src.schemas import Market  # lazy to avoid any circular-import risk

        contract_family = classification["contract_family"] if classification else "other"
        is_primary_sample = contract_family != "other"

        # category partition key: use contract_family when classified, else fall back to arg
        effective_category = contract_family if classification else category

        tags = _extract_tags(raw.get("tags"))

        token_ids: list[str] = _json.loads(raw.get("clobTokenIds") or "[]")
        yes_token_id = token_ids[0] if len(token_ids) > 0 else ""
        no_token_id = token_ids[1] if len(token_ids) > 1 else ""

        # Resolution is encoded in outcomePrices (["1","0"] -> YES, ["0","1"] -> NO);
        # the `winner` field is never populated by the /events endpoint.
        winner = raw.get("winner") or ""
        outcome_prices = _json.loads(raw.get("outcomePrices") or "[]")
        if winner in ("Yes", "YES"):
            resolved_outcome = "YES"
        elif winner in ("No", "NO"):
            resolved_outcome = "NO"
        elif len(outcome_prices) == 2 and float(outcome_prices[0]) == 1.0:
            resolved_outcome = "YES"
        elif len(outcome_prices) == 2 and float(outcome_prices[1]) == 1.0:
            resolved_outcome = "NO"
        else:
            resolved_outcome = "INVALID"

        volume_raw = raw.get("volume") or raw.get("volumeNum") or 0.0

        company_name = classification.get("company_name") if classification else None
        ticker = classification.get("ticker") if classification else None
        company_id = classification.get("company_id", "") if classification else ""

        strike_price = strike_fields.get("strike_price") if strike_fields else None
        strike_direction = strike_fields.get("strike_direction") if strike_fields else None
        price_expiry_month = strike_fields.get("price_expiry_month") if strike_fields else None

        volume_1wk = float(raw.get("volume1wk") or 0.0)
        volume_1mo = float(raw.get("volume1mo") or 0.0)

        return Market(
            market_id=raw["conditionId"],
            slug=raw.get("slug") or raw["conditionId"],
            question=raw.get("question", ""),
            description=raw.get("description") or "",
            category=effective_category,
            tags=tags,
            created_at=_parse_dt(raw.get("startDate")) or datetime.now(tz=timezone.utc),
            end_at=_parse_dt(raw.get("endDate")) or datetime.now(tz=timezone.utc),
            resolved_at=_parse_dt(raw.get("resolutionDate") or raw.get("resolvedDate")),
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            resolved_outcome=resolved_outcome,
            total_volume_usdc=float(volume_raw),
            contract_family=contract_family,
            parent_event_id=None,
            is_primary_sample=is_primary_sample,
            company_name=company_name,
            ticker=ticker,
            company_id=company_id,
            strike_price=strike_price,
            strike_direction=strike_direction,
            price_expiry_month=price_expiry_month,
            group_id="",
            group_role="standalone",
            volume_1wk=volume_1wk,
            volume_1mo=volume_1mo,
        )
