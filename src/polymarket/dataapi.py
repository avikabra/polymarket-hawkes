"""Polymarket Data-API trade client — replaces the deprecated Goldsky subgraph.

Endpoint: GET https://data-api.polymarket.com/trades
  market=<conditionId>  takerOnly=true  limit<=10000  offset<=10000 (400 past cap)
  start/end = epoch-second window bounds.

Completeness strategy: pure time-bisection. We never page past offset 0 — instead,
if a [start,end) window returns a full page (>= limit), we split the window and recurse.
This sidesteps the 10,000-offset cap entirely (the cap is loud — HTTP 400 — but with
offset fixed at 0 we never reach it) and is verifiably complete: sum(size) over
takerOnly=true trades reconciles to Gamma's total_volume_usdc (see
reports/trade_source_decision.md).

takerOnly=true yields exactly one row per trade (taker perspective); takerOnly=false
double-counts (maker+taker). `price` is the traded asset's own price in [0,1].
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

_BASE = "https://data-api.polymarket.com/trades"
_MAX_LIMIT = 10_000
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}
# Statuses that mean "the window was too heavy" — split it rather than give up.
_TOO_HEAVY_STATUS = {408, 504, 502, 503}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    # Retry transient HTTP statuses (rate limit / 5xx); a 400 (offset cap etc.) is fatal.
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
    async def _request(self, params: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(_BASE, params=params)
            resp.raise_for_status()  # 4xx/5xx -> HTTPStatusError (retried only if transient)
            return resp.json()

    async def _fetch_window(self, condition_id: str, lo: int, hi: int) -> list[dict]:
        key = f"dataapi:trades:{condition_id}:{lo}:{hi}"
        cached = self._cache.get(key)
        if cached is not None:
            return json.loads(cached)
        params = {
            "market": condition_id,
            "takerOnly": "true",
            "limit": _MAX_LIMIT,
            "offset": 0,
            "start": lo,
            "end": hi,
        }
        page = await self._request(params)
        await asyncio.sleep(self._req_sleep)  # polite pacing on live (non-cached) calls only
        # Only cache a window we know is complete (not a full page that will be bisected).
        if len(page) < _MAX_LIMIT:
            self._cache.set(key, json.dumps(page).encode())
        return page

    async def iter_market_fills(
        self, condition_id: str, start_ts: int, end_ts: int
    ) -> AsyncIterator[dict]:
        """Yield every takerOnly trade for a market's conditionId in [start_ts, end_ts).

        Both YES and NO token fills are returned (the Data-API keys on conditionId).
        Windows that return a full page are bisected until each is complete; a window
        that cannot be bisected further (1-second) yet still overflows raises loudly.
        """
        seen: set[tuple] = set()
        stack: list[tuple[int, int]] = [(int(start_ts), int(end_ts))]
        while stack:
            lo, hi = stack.pop()
            if hi <= lo:
                continue
            try:
                page = await self._fetch_window(condition_id, lo, hi)
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                # A timeout (or heavy-server status) after retries means the window is
                # too big to serve — split it so each half is lighter. Only a 1-second
                # window that still fails is a real error.
                too_heavy = isinstance(exc, httpx.TimeoutException) or (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code in _TOO_HEAVY_STATUS
                )
                if too_heavy and hi - lo > 1:
                    mid = (lo + hi) // 2
                    stack.append((mid, hi))
                    stack.append((lo, mid))
                    self._log.warning(
                        "window too heavy, bisecting",
                        extra={"market": condition_id, "lo": lo, "hi": hi},
                    )
                    continue
                raise
            if len(page) >= _MAX_LIMIT:
                if hi - lo <= 1:
                    raise RuntimeError(
                        f"market {condition_id}: >= {_MAX_LIMIT} trades within a 1s "
                        f"window [{lo},{hi}) — cannot page further; source needs revisiting"
                    )
                mid = (lo + hi) // 2
                stack.append((mid, hi))
                stack.append((lo, mid))
                continue
            for t in page:
                k = (
                    t.get("transactionHash", ""),
                    t.get("asset", ""),
                    int(t["timestamp"]),
                    str(t["size"]),
                    str(t["price"]),
                )
                if k in seen:
                    continue
                seen.add(k)
                yield t


def normalize_dataapi_fill(raw: dict, market_id: str, yes_token_id: str) -> Trade | None:
    """Convert a Data-API trade dict into a pipeline Trade (YES-terms log-odds).

    `price` is the traded asset's own probability; convert to YES terms so log-odds
    are consistent across both tokens of a market. size_usdc = size * price (actual
    USDC paid), matching the Goldsky normalizer's semantics.
    """
    asset = raw.get("asset", "")
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

    tx = raw.get("transactionHash", "")
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
        side=side,
        tx_hash=tx,
    )
