"""Shared glue for the Thread 1 joint (embedding + liquidity) score.

Used by both scripts/09_llm_verify_matches.py's `--joint` path and
scripts/09b_matching_ablation.py, so the exact same
"gather a group's member bars -> compute_liquidity_response -> verify_pair_joint"
pipeline runs in both places rather than being duplicated.

Design gap not specified in novel_math_design.md — flagging per plan instructions:
`compute_liquidity_response` (src/matching/liquidity_signal.py) takes a single
scalar `market_resolved_at` applied uniformly to every member market inside its
loop; it has no per-member notion (matching its own price_impact aggregation,
which is already a single max-|y_logit| across members). But a group's member
markets can each resolve at different times. `group_resolved_at` below resolves
this by taking the EARLIEST member resolution (min) — the conservative choice:
since the group-level price_impact is a max across members, anchoring window
validity to the first member to resolve avoids ever treating a window as valid
once any one member in the group has already settled. This is more conservative
than scripts/12_assemble_dataset.py's per-market resolved_at (each market's own
window is checked only against its own resolution).
"""

from __future__ import annotations

import pandas as pd

from src.matching._types import VerificationResult
from src.matching.joint_verifier import verify_pair_joint
from src.matching.liquidity_signal import compute_liquidity_response
from src.polymarket.company_filter import COMPANY_DICT, entity_grounding_match, gdelt_entity_aliases
from src.utils import load_bars


def parse_article_ts(pub_at: str | None) -> pd.Timestamp | None:
    """article_published_at (candidates table, ISO string) -> tz-aware Timestamp."""
    if not pub_at:
        return None
    ts = pd.Timestamp(pub_at)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts


def market_resolved_at_map(universe_df: pd.DataFrame) -> dict[str, pd.Timestamp | None]:
    """market_id -> resolved_at, falling back to end_at when resolved_at is missing.

    Exactly mirrors scripts/12_assemble_dataset.py's per-market resolved_at logic
    (universe.parquet's resolved_at is NaT for all rows even though every market
    genuinely resolved — end_at is the best available proxy; see script 12's
    inline comment for the full data-gap explanation).
    """
    result: dict[str, pd.Timestamp | None] = {}
    for _, row in universe_df.iterrows():
        resolved_at_raw = row.get("resolved_at")
        resolved_at = (
            pd.Timestamp(resolved_at_raw)
            if resolved_at_raw and pd.notna(resolved_at_raw)
            else None
        )
        if resolved_at is None:
            end_at_raw = row.get("end_at")
            if end_at_raw and pd.notna(end_at_raw):
                resolved_at = pd.Timestamp(end_at_raw)
        if resolved_at is not None and resolved_at.tzinfo is None:
            resolved_at = resolved_at.tz_localize("UTC")
        result[str(row["market_id"])] = resolved_at
    return result


def group_member_map(contract_groups_df: pd.DataFrame) -> dict[str, list[str]]:
    """group_id -> member market_ids, per contract_groups.parquet."""
    return {
        str(row["group_id"]): [str(m) for m in row["member_market_ids"]]
        for _, row in contract_groups_df.iterrows()
    }


def group_company_aliases_map(contract_groups_df: pd.DataFrame) -> dict[str, list[str]]:
    """group_id -> GDELT-safe entity aliases (company_filter.gdelt_entity_aliases)
    for that group's company_name, for the entity-grounding term in
    verify_pair_joint. Falls back to [company_name] if it's not a COMPANY_DICT key
    (should not happen — company_name is set from COMPANY_DICT at classification
    time — but fails open rather than raising, matching this module's other maps)."""
    result: dict[str, list[str]] = {}
    for _, row in contract_groups_df.iterrows():
        canon = str(row["company_name"])
        aliases = COMPANY_DICT.get(canon, [canon])
        result[str(row["group_id"])] = gdelt_entity_aliases(canon, aliases)
    return result


def group_resolved_at(
    member_ids: list[str], resolved_at_map: dict[str, pd.Timestamp | None]
) -> pd.Timestamp | None:
    """Earliest resolved_at among a group's member markets (see module docstring)."""
    candidates = [
        resolved_at_map[mid] for mid in member_ids if resolved_at_map.get(mid) is not None
    ]
    return min(candidates) if candidates else None


def load_group_member_bars(member_ids: list[str]) -> dict[str, pd.DataFrame]:
    """One market's bars are only ever loaded once (load_bars is lru_cache'd)."""
    return {mid: load_bars(mid) for mid in member_ids}


def score_pair_joint(
    embedding_score: float,
    article_ts: pd.Timestamp | None,
    timestamp_precision: str,
    member_bars: dict[str, pd.DataFrame],
    market_resolved_at: pd.Timestamp | None,
    entities: list[str] | None = None,
    company_aliases: list[str] | None = None,
) -> tuple[VerificationResult, dict]:
    """Compute the joint (embedding + liquidity + entity-grounding) verification
    for one (group, article) pair. Returns (VerificationResult, raw
    liquidity_response dict) — the latter is kept for callers that want
    volume_z/price_impact directly (e.g. diagnostics) without recomputing.

    entities/company_aliases are optional and both default to producing
    entity_match=False (callers that don't pass them get the original two-term
    score back, unchanged) — see joint_verifier.py's 2026-10-05 extension note.
    """
    liquidity = compute_liquidity_response(
        member_bars=member_bars,
        article_ts=article_ts,
        timestamp_precision=timestamp_precision,
        market_resolved_at=market_resolved_at,
    )
    entity_match = entity_grounding_match(entities or [], company_aliases or [])
    result = verify_pair_joint(
        embedding_score=embedding_score,
        liquidity_z=liquidity["volume_z"],
        price_impact=liquidity["price_impact"],
        entity_match=entity_match,
    )
    return result, liquidity
