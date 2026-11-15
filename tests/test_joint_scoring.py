"""Tests for src/matching/joint_scoring.py — entity-grounding wiring (2026-10-05)."""

import pandas as pd

from src.matching.joint_scoring import group_company_aliases_map, score_pair_joint


def test_group_company_aliases_map_uses_company_dict_aliases():
    contract_groups_df = pd.DataFrame([
        {"group_id": "g1", "company_name": "Apple"},
        {"group_id": "g2", "company_name": "Tesla"},
    ])
    result = group_company_aliases_map(contract_groups_df)
    assert "g1" in result and "g2" in result
    assert any("Apple" in a or a == "Apple" for a in result["g1"])


def test_group_company_aliases_map_unknown_company_falls_back_to_name():
    contract_groups_df = pd.DataFrame([{"group_id": "g1", "company_name": "NotARealCompany"}])
    result = group_company_aliases_map(contract_groups_df)
    assert result["g1"] == ["NotARealCompany"]


def test_score_pair_joint_entity_match_raises_score_with_empty_bars():
    """member_bars={} degrades liquidity_z=0.0, price_impact=None (per
    compute_liquidity_response's documented empty-frame fallback) so this isolates
    the entity-grounding term's effect without needing real bars fixtures."""
    no_match_result, _ = score_pair_joint(
        embedding_score=0.5,
        article_ts=None,
        timestamp_precision="day",
        member_bars={},
        market_resolved_at=None,
        entities=["Microsoft"],
        company_aliases=["Apple"],
    )
    match_result, _ = score_pair_joint(
        embedding_score=0.5,
        article_ts=None,
        timestamp_precision="day",
        member_bars={},
        market_resolved_at=None,
        entities=["Apple Inc"],
        company_aliases=["Apple"],
    )
    assert match_result.match_strength > no_match_result.match_strength


def test_score_pair_joint_defaults_entities_to_no_match():
    """Callers that don't pass entities/company_aliases (every existing call site
    before 2026-10-05) get entity_match=False, i.e. unchanged behavior."""
    result, _ = score_pair_joint(
        embedding_score=0.5,
        article_ts=None,
        timestamp_precision="day",
        member_bars={},
        market_resolved_at=None,
    )
    assert "entity_match=False" in result.reasoning
