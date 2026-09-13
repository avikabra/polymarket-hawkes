import hashlib
import os
from pathlib import Path


class DiskCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self._root = Path(cache_dir)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self._root / digest[:2] / f"{digest}.cache"

    def get(self, key: str) -> bytes | None:
        p = self._path(key)
        # A zero-byte file is a corrupt entry from an interrupted/ENOSPC write;
        # treat it as a miss so the caller re-fetches instead of parsing "".
        if not p.exists() or p.stat().st_size == 0:
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
