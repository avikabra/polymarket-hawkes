import json
from typing import AsyncIterator

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.utils import DiskCache, get_logger

_GQL_URL = (
    "https://api.goldsky.com/api/public/project_cl6mb8i9h0003e201j6li0diw"
    "/subgraphs/polymarket-orderbook-resync/prod/gn"
)
_PAGE_SIZE = 1000

_QUERY = """\
query GetFills($token: String!, $ts_gte: BigInt!, $ts_lt: BigInt!, $li_gt: Int!, $first: Int!) {
  orderFilledEvents(
    first: $first, orderBy: timestamp, orderDirection: asc,
    where: { %s: $token, timestamp_gte: $ts_gte, timestamp_lt: $ts_lt, logIndex_gt: $li_gt }
  ) {
    timestamp logIndex blockNumber transactionHash
    maker taker makerAssetId takerAssetId
    makerAmountFilled takerAmountFilled
  }
}
"""

_MAKER_QUERY = _QUERY % "makerAssetId"
_TAKER_QUERY = _QUERY % "takerAssetId"


class GoldskyClient:
    def __init__(self, cache_dir: str = "data/.cache/goldsky") -> None:
        self._cache = DiskCache(cache_dir)
        self._log = get_logger(__name__)

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _gql(self, query: str, variables: dict) -> list[dict]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(_GQL_URL, json={"query": query, "variables": variables})
            resp.raise_for_status()
        return resp.json().get("data", {}).get("orderFilledEvents", [])

    async def _fetch_page(
        self,
        query: str,
        label: str,
        token: str,
        ts_gte: int,
        ts_lt: int,
        li_gt: int,
        page: int,
    ) -> list[dict]:
        cache_key = f"goldsky:{label}:{token}:{ts_gte}:{ts_lt}:{page}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        variables = {
            "token": token,
            "ts_gte": str(ts_gte),
            "ts_lt": str(ts_lt),
            "li_gt": li_gt,
            "first": _PAGE_SIZE,
        }
        data = await self._gql(query, variables)
        self._cache.set(cache_key, json.dumps(data).encode())
        return data

    async def iter_fills(
        self, token_id: str, start_ts: int, end_ts: int
    ) -> AsyncIterator[dict]:
        seen: set[str] = set()

        for query, label in ((_MAKER_QUERY, "maker"), (_TAKER_QUERY, "taker")):
            cursor_ts, cursor_li, page = start_ts, -1, 0
            while True:
                fills = await self._fetch_page(
                    query, label, token_id, cursor_ts, end_ts, cursor_li, page
                )
                if not fills:
                    break
                for fill in fills:
                    key = f"{fill['transactionHash']}:{fill['logIndex']}"
                    if key not in seen:
                        seen.add(key)
                        yield fill
                if len(fills) < _PAGE_SIZE:
                    break
                last = fills[-1]
                cursor_ts = int(last["timestamp"])
                cursor_li = int(last["logIndex"])
                page += 1
