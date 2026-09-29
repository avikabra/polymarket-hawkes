"""Tests for src/matching/joint_verifier.py."""

import math

import pytest

from src.matching._types import VerificationResult
from src.matching.joint_verifier import verify_pair_joint
from src.matching.rule_verifier import verify_pair_rule


def test_monotone_in_embedding_score():
    low = verify_pair_joint(embedding_score=0.3, liquidity_z=0.0, price_impact=None)
    high = verify_pair_joint(embedding_score=0.9, liquidity_z=0.0, price_impact=None)
    assert high.match_strength > low.match_strength


def test_monotone_in_liquidity_z():
    low = verify_pair_joint(embedding_score=0.5, liquidity_z=-2.0, price_impact=None)
    high = verify_pair_joint(embedding_score=0.5, liquidity_z=2.0, price_impact=None)
    assert high.match_strength > low.match_strength


def test_known_output_regression():
    """Independent second implementation path: same closed-form formula, computed
    directly with math.log/math.exp here rather than calling the module's
    internal _logit/_sigmoid helpers."""
    embedding_score = 0.8
    liquidity_z = 1.0
    w1 = w2 = 1.0

    clipped = min(max(embedding_score, 0.001), 0.999)
    expected_logit = math.log(clipped / (1.0 - clipped))
    expected_quality_logit = w1 * expected_logit + w2 * liquidity_z
    expected_strength = 1.0 / (1.0 + math.exp(-expected_quality_logit))

    result = verify_pair_joint(
        embedding_score=embedding_score, liquidity_z=liquidity_z, price_impact=None,
        w1=w1, w2=w2,
    )
    assert result.match_strength == pytest.approx(round(expected_strength, 4), abs=1e-4)
    assert result.is_match == (expected_strength >= 0.50)


def test_clips_extreme_embedding_score_no_inf():
    result = verify_pair_joint(embedding_score=1.0, liquidity_z=0.0, price_impact=None)
    assert math.isfinite(result.match_strength)
    result_zero = verify_pair_joint(embedding_score=0.0, liquidity_z=0.0, price_impact=None)
    assert math.isfinite(result_zero.match_strength)


def test_positive_price_impact_gives_bullish_directional_impact():
    result = verify_pair_joint(embedding_score=0.6, liquidity_z=0.0, price_impact=0.5)
    assert result.directional_impact == 1


def test_negative_price_impact_gives_bearish_directional_impact():
    result = verify_pair_joint(embedding_score=0.6, liquidity_z=0.0, price_impact=-0.5)
    assert result.directional_impact == -1


def test_none_price_impact_gives_neutral_directional_impact():
    result = verify_pair_joint(embedding_score=0.6, liquidity_z=0.0, price_impact=None)
    assert result.directional_impact == 0


def test_is_match_threshold():
    # match_strength == 0.5 exactly when embedding_score=0.5 (logit=0) and liquidity_z=0
    boundary = verify_pair_joint(embedding_score=0.5, liquidity_z=0.0, price_impact=None)
    assert boundary.match_strength == pytest.approx(0.5, abs=1e-6)
    assert boundary.is_match is True  # >= threshold

    below = verify_pair_joint(embedding_score=0.5, liquidity_z=-0.1, price_impact=None)
    assert below.is_match is False


def test_output_schema_matches_rule_verifier():
    joint_result = verify_pair_joint(embedding_score=0.7, liquidity_z=0.5, price_impact=0.1)
    rule_result = verify_pair_rule(0.7, "Team wins", None)

    assert type(joint_result) is type(rule_result) is VerificationResult
    for field in VerificationResult.model_fields:
        assert type(getattr(joint_result, field)) is type(getattr(rule_result, field))
