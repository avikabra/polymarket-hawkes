"""Polymarket Data-API v2 trade client — replaces the deprecated Goldsky subgraph (and retired v1).

Endpoint: GET https://data-api.polymarket.com/v2/trades
  condition=<conditionId>  taker_only=true  limit<=1000 (first page only)  cursor=<opaque>
  Response: {"data": [Trade...], "pagination": {"has_more", "next_cursor"|null, ...}}.

Completeness strategy: cursor pagination. The v2 condition shape ignores start/end (fixed
three-year lookback), so one market is walked page by page via pagination.next_cursor
(identical filters re-sent every page) and the [start_ts, end_ts) window is applied
client-side. Rows are deduplicated, so row order does not matter. v2 has no offset
(HTTP 400 if sent, even 0).

taker_only=true yields exactly one row per trade (taker perspective); false double-counts
(maker+taker). `price` is the traded token's own price in [0,1]; `size` is shares.
Fields are snake_case: token_id (was asset), transaction_hash (was transactionHash).
"""
import asyncio
import hashlib
import json
import math
from typing import AsyncIterator

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.schemas import Trade
from src.utils import DiskCache, get_logger

_BASE = "https://data-api.polymarket.com/v2/trades"
_PAGE_LIMIT = 1000
# v2 drops fills below filter_amount tokens (default 0.01; 0 means the default), so pass a
# tiny positive value to keep dust fills that v1 returned.
_MIN_FILL = 1e-9
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    # Retry transient HTTP statuses (rate limit / 5xx); a 400/410 is fatal.
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in _RETRY_STATUS
    )


class DataApiClient:
    def __init__(self, cache_dir: str = "data/.cache/dataapi", req_sleep: float = 0.15) -> None:
        self._cache = DiskCache(cache_dir)
        self._log = get_logger(__name__)
        self._req_sleep = req_sleep

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(8),  # ~3+ min of backoff absorbs brief DNS/network blips
        reraise=True,
    )
    async def _request(self, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()  # 4xx/5xx -> HTTPStatusError (retried only if transient)
            return resp.json()

    async def _fetch_page(self, condition_id: str, cursor: str | None) -> dict:
        key = f"dataapi:v2:trades:{condition_id}:{cursor or ''}"
        cached = self._cache.get(key)
        if cached is not None:
            return json.loads(cached)
        params = {
            "condition": condition_id,
            "taker_only": "true",
            "filter_amount": _MIN_FILL,
            "limit": _PAGE_LIMIT,
        }
        if cursor:
            params["cursor"] = cursor
        body = await self._request(params)
        await asyncio.sleep(self._req_sleep)  # polite pacing on live (non-cached) calls only
        self._cache.set(key, json.dumps(body).encode())
        return body

    async def iter_market_fills(
        self, condition_id: str, start_ts: int, end_ts: int
    ) -> AsyncIterator[dict]:
        """Yield every takerOnly trade for a market's conditionId in [start_ts, end_ts).

        Both YES and NO token fills are returned (the Data-API keys on conditionId).
        Walks pagination.next_cursor until null; the time window is filtered client-side.
        """
        seen: set[tuple] = set()
        cursor: str | None = None
        while True:
            body = await self._fetch_page(condition_id, cursor)
            for t in body["data"] or []:
                ts = int(t["timestamp"])
                if not (start_ts <= ts < end_ts):
                    continue
                k = (
                    t.get("transaction_hash", ""),
                    t.get("token_id", ""),
                    ts,
                    str(t["size"]),
                    str(t["price"]),
                )
                if k in seen:
                    continue
                seen.add(k)
                yield t
            cursor = body["pagination"]["next_cursor"]
            if not cursor:
                return


def normalize_dataapi_fill(raw: dict, market_id: str, yes_token_id: str) -> Trade | None:
    """Convert a Data-API trade dict into a pipeline Trade (YES-terms log-odds).

    `price` is the traded asset's own probability; convert to YES terms so log-odds
    are consistent across both tokens of a market. size_usdc = size * price (actual
    USDC paid), matching the Goldsky normalizer's semantics.
    """
    asset = raw.get("token_id", "")
    try:
        size = float(raw["size"])
        price = float(raw["price"])
    except (KeyError, TypeError, ValueError):
        return None
    if size <= 0 or not (0.0 < price < 1.0000001):
        return None

    is_yes = asset == yes_token_id
    p_yes = price if is_yes else 1.0 - price
    price_raw = max(0.001, min(0.999, p_yes))
    log_odds = math.log(price_raw / (1.0 - price_raw))

    taker_side = raw.get("side", "")  # BUY/SELL, taker perspective (takerOnly=true)
    if is_yes:
        side = "YES_BUY" if taker_side == "BUY" else "YES_SELL"
    else:
        # Buying the NO token is selling YES exposure, and vice versa.
        side = "YES_SELL" if taker_side == "BUY" else "YES_BUY"

    tx = raw.get("transaction_hash", "")
    # No logIndex in this feed; derive a stable intra-second tiebreaker.
    log_index = int(
        hashlib.sha256(f"{tx}:{asset}:{size}:{price}".encode()).hexdigest()[-8:], 16
    )

    return Trade(
        market_id=market_id,
        token_id=asset,
        ts_s=int(raw["timestamp"]),
        log_index=log_index,
        price_raw=price_raw,
        log_odds=log_odds,
        size_usdc=size * price,
        size_shares=size,
        side=side,
        tx_hash=tx,
    )
