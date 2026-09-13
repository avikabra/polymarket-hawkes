"""scope.py — Corpus/universe scope guard.

Downstream scripts (07-09, 12) read the raw news corpus (GDELT + feeds) and the
market universe directly. If the corpus was collected for a different universe
(e.g. a stale NFL corpus while the universe now holds 6,928 company markets),
matching against it silently produces meaningless results. `assert_covers`
makes that fail loudly instead.

Coverage is a SUPERSET check, not equality: the corpus may have extra
companies or a wider date window than the universe — the universe grows over
time, and strict equality would invalidate an expensive corpus on every
addition. It only fails when the corpus is missing something the universe
needs, or when its scope is unknown (no `_SCOPE.json` written yet).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

_SCOPE_FILENAME = "_SCOPE.json"
_TRUNCATE_AT = 20


def write_scope(directory: Path, company_ids: Iterable[str], window: tuple[str, str]) -> None:
    """Write `_SCOPE.json` into `directory` recording what this corpus covers.

    Stores the sorted list of company_ids (not a hash or count alone) so a
    coverage mismatch is diagnosable later without recomputing the corpus,
    plus the covered date window as `[window[0], window[1])` ISO-8601 strings.
    """
    ids_sorted = sorted(set(company_ids))
    payload = {
        "company_ids": ids_sorted,
        "count": len(ids_sorted),
        "window_start": window[0],
        "window_end": window[1],
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / _SCOPE_FILENAME).write_text(json.dumps(payload, indent=2))


def read_scope(directory: Path) -> dict | None:
    """Read `_SCOPE.json` from `directory`, or None if it hasn't been written yet."""
    path = directory / _SCOPE_FILENAME
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _parse(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp for ordering, ignoring timezone offsets.

    The scope guard only needs coarse (day-level) window coverage, so a naive
    comparison is enough and it avoids crashing on tz-aware vs. tz-naive mixes
    between the universe and a corpus written by a different script.
    """
    dt = datetime.fromisoformat(ts)
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def assert_covers(
    corpus_dirs: Path | Iterable[Path],
    universe_ids: Iterable[str],
    universe_window: tuple[str, str],
) -> None:
    """Raise RuntimeError unless the corpus scope covers the market universe.

    `corpus_dirs` may be a single directory or several (e.g. GDELT + feeds);
    their `_SCOPE.json` coverage is unioned before comparing against the
    universe. Each directory must have its own `_SCOPE.json` — a missing
    sidecar means that source's scope is unknown (today's stale-corpus
    situation) and always fails, it never silently passes.
    """
    dirs = [corpus_dirs] if isinstance(corpus_dirs, Path) else list(corpus_dirs)

    corpus_ids: set[str] = set()
    starts: list[datetime] = []
    ends: list[datetime] = []
    for d in dirs:
        scope = read_scope(d)
        if scope is None:
            raise RuntimeError(
                f"{d / _SCOPE_FILENAME} not found — this corpus's scope is unknown "
                "(likely stale or never scoped). Re-run the news collection scripts "
                "(04/05) to regenerate it before matching against the market universe."
            )
        corpus_ids.update(scope["company_ids"])
        starts.append(_parse(scope["window_start"]))
        ends.append(_parse(scope["window_end"]))

    missing = sorted(set(universe_ids) - corpus_ids)
    if missing:
        shown = missing[:_TRUNCATE_AT]
        more = f" (+{len(missing) - _TRUNCATE_AT} more)" if len(missing) > _TRUNCATE_AT else ""
        raise RuntimeError(
            f"News corpus does not cover {len(missing)} of the universe's company_ids: "
            f"{shown}{more}. Re-run the news collection scripts (04/05) to extend coverage."
        )

    corpus_start, corpus_end = min(starts), max(ends)
    uni_start, uni_end = _parse(universe_window[0]), _parse(universe_window[1])
    if corpus_start > uni_start or corpus_end < uni_end:
        raise RuntimeError(
            f"News corpus window [{corpus_start.isoformat()}, {corpus_end.isoformat()}] "
            f"does not cover universe window [{uni_start.isoformat()}, {uni_end.isoformat()}]. "
            "Re-run the news collection scripts (04/05) to extend the date range."
        )
