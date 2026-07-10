"""Tests for rule-based candidate verifier."""

import pytest
from src.matching.rule_verifier import verify_pair_rule


def test_above_threshold_is_match():
    result = verify_pair_rule(0.75, "Team wins championship", None)
    assert result.is_match is True
    assert result.match_strength == pytest.approx(0.75, abs=1e-4)


def test_below_threshold_not_match():
    result = verify_pair_rule(0.30, "Unrelated article", None)
    assert result.is_match is False


def test_bullish_keywords():
    result = verify_pair_rule(0.6, "Team wins and beats rival", "Strong victory")
    assert result.directional_impact == 1


def test_bearish_keywords():
    result = verify_pair_rule(0.6, "Player injured, out for season", None)
    assert result.directional_impact == -1


def test_mixed_keywords_neutral():
    result = verify_pair_rule(0.6, "Win or lose, team fights on", None)
    assert result.directional_impact == 0


def test_no_keywords_neutral():
    result = verify_pair_rule(0.6, "Preview of upcoming matchup", None)
    assert result.directional_impact == 0


def test_quantitative_news_type():
    result = verify_pair_rule(0.6, "QB throws for 312 yards", None)
    assert result.news_type == "quantitative"


def test_qualitative_news_type():
    result = verify_pair_rule(0.6, "Coach praises team effort", None)
    assert result.news_type == "qualitative"


def test_custom_threshold():
    result = verify_pair_rule(0.45, "Team wins", None, match_threshold=0.40)
    assert result.is_match is True


def test_reasoning_contains_score():
    result = verify_pair_rule(0.62, "Team wins", None)
    assert "0.62" in result.reasoning or "rule-based" in result.reasoning
