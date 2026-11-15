import hashlib
import os
import time
from pathlib import Path


class DiskCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self._root = Path(cache_dir)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self._root / digest[:2] / f"{digest}.cache"

    def get(self, key: str, max_age_seconds: float | None = None) -> bytes | None:
        p = self._path(key)
        # A zero-byte file is a corrupt entry from an interrupted/ENOSPC write;
        # treat it as a miss so the caller re-fetches instead of parsing "".
        if not p.exists() or p.stat().st_size == 0:
            return None
        # Opt-in TTL: default (None) is the original no-expiry behavior, so
        # existing callers (BigQuery, Gamma, Goldsky/Data-API, article bodies)
        # are unaffected unless they explicitly pass a max age. Only live,
        # cheap-to-refetch sources like RSS should opt in.
        if max_age_seconds is not None and time.time() - p.stat().st_mtime > max_age_seconds:
            return None
        return p.read_bytes()

    def set(self, key: str, value: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: a failed/partial write (e.g. ENOSPC) leaves the temp file,
        # never a truncated cache entry that would crash a later resume.
        tmp = p.with_suffix(f".cache.tmp.{os.getpid()}")
        try:
            tmp.write_bytes(value)
            os.replace(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)
