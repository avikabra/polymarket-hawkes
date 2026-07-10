"""De-duplicate verified articles per market into NewsEvent clusters.

Clustering criteria (applied in order):
  1. Same market_id
  2. Article timestamps within 4 hours of each other
  3. BGE-large cosine similarity > 0.85 (uses matching embeddings, not analysis embeddings)
  4. Overlapping GDELT entities (if available)

Each cluster → one NewsEvent.
The canonical_ts is the earliest minute-precision timestamp in the cluster;
falls back to the earliest day-precision timestamp if no minute-precision member exists.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Literal

import numpy as np
import pandas as pd

from src.schemas import NewsEvent

_FOUR_HOURS = timedelta(hours=4)
_COS_THRESHOLD = 0.85


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _entities(raw_metadata_json: str) -> set[str]:
    try:
        meta = json.loads(raw_metadata_json or "{}")
        persons = meta.get("persons", [])
        orgs = meta.get("orgs", [])
        return {e.lower() for e in (persons + orgs) if e}
    except Exception:
        return set()


def _should_merge(
    a: dict,
    b: dict,
    emb_map: dict[str, np.ndarray],
) -> bool:
    """Return True if articles a and b belong in the same cluster."""
    # 1. Time window
    ts_a = pd.Timestamp(a["article_published_at"]) if a.get("article_published_at") else None
    ts_b = pd.Timestamp(b["article_published_at"]) if b.get("article_published_at") else None
    if ts_a is None or ts_b is None:
        return False  # cannot cluster without timestamps
    if abs(ts_a - ts_b) > _FOUR_HOURS:
        return False

    # 2. Cosine similarity on matching embeddings (if available)
    ea = emb_map.get(a["article_id"])
    eb = emb_map.get(b["article_id"])
    if ea is not None and eb is not None:
        if _cosine(ea, eb) < _COS_THRESHOLD:
            return False

    # 3. Entity overlap (if any entities exist)
    ents_a = _entities(a.get("raw_metadata_json", "{}"))
    ents_b = _entities(b.get("raw_metadata_json", "{}"))
    if ents_a and ents_b and not ents_a.intersection(ents_b):
        return False

    return True


def _canonical_ts(members: list[dict]) -> tuple[pd.Timestamp, Literal["minute", "day"]]:
    """Return (earliest_ts, precision) for a cluster."""
    minute_ts = [
        pd.Timestamp(m["article_published_at"])
        for m in members
        if m.get("timestamp_precision") == "minute" and m.get("article_published_at")
    ]
    if minute_ts:
        return min(minute_ts), "minute"
    day_ts = [
        pd.Timestamp(m["article_published_at"])
        for m in members
        if m.get("article_published_at")
    ]
    return (min(day_ts), "day") if day_ts else (pd.Timestamp.now("UTC"), "day")


def _majority_vote(values: list, default):
    if not values:
        return default
    counts: dict = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=lambda k: counts[k])


def cluster_market(
    verified_rows: list[dict],
    emb_map: dict[str, np.ndarray],
) -> list[NewsEvent]:
    """Cluster verified articles for a single market → list[NewsEvent]."""
    if not verified_rows:
        return []

    # Union-find style greedy clustering
    n = len(verified_rows)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    # Sort by timestamp so the window check is efficient
    rows_sorted = sorted(
        verified_rows,
        key=lambda r: pd.Timestamp(r["article_published_at"]) if r.get("article_published_at") else pd.Timestamp.min,
    )

    for i in range(n):
        for j in range(i + 1, n):
            ts_j = pd.Timestamp(rows_sorted[j].get("article_published_at", "")) if rows_sorted[j].get("article_published_at") else None
            ts_i = pd.Timestamp(rows_sorted[i].get("article_published_at", "")) if rows_sorted[i].get("article_published_at") else None
            # Once j is more than 4h ahead, no need to check further
            if ts_i and ts_j and (ts_j - ts_i) > _FOUR_HOURS:
                break
            if _should_merge(rows_sorted[i], rows_sorted[j], emb_map):
                union(i, j)

    # Group by root
    clusters: dict[int, list[dict]] = {}
    for i, row in enumerate(rows_sorted):
        clusters.setdefault(find(i), []).append(row)

    events = []
    market_id = verified_rows[0]["market_id"]
    for members in clusters.values():
        canonical_ts, precision = _canonical_ts(members)
        directional_impacts = [m.get("directional_impact", 0) for m in members]
        news_types = [m.get("news_type", "ambiguous") for m in members]

        events.append(NewsEvent(
            event_id=str(uuid.uuid4()),
            market_id=market_id,
            canonical_ts=canonical_ts.to_pydatetime(),
            timestamp_precision=precision,
            member_article_ids=[m["article_id"] for m in members],
            member_count=len(members),
            sources=list({m.get("source", "unknown") for m in members}),
            consensus_directional_impact=_majority_vote(directional_impacts, 0),
            dominant_news_type=_majority_vote(news_types, "ambiguous"),
        ))

    return events
