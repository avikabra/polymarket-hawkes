import asyncio
import time


class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        self._rate = rate  # tokens/second
        self._capacity = capacity
        self._tokens = capacity
        self._last = time.monotonic()

    async def acquire(self, tokens: float = 1.0) -> None:
        while True:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            wait = (tokens - self._tokens) / self._rate
            await asyncio.sleep(wait)
