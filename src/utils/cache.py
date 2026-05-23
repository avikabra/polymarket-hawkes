import hashlib
from pathlib import Path


class DiskCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self._root = Path(cache_dir)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self._root / digest[:2] / f"{digest}.cache"

    def get(self, key: str) -> bytes | None:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def set(self, key: str, value: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value)
