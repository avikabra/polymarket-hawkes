"""Tests for src/matching/llm_verifier.py using a mocked Anthropic client."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.matching.llm_verifier import VerificationResult, _extract_json, verify_pair


def test_extract_json_plain():
    raw = '{"is_match": true, "match_strength": 0.9, "directional_impact": 1, "magnitude": 0.7, "news_type": "quantitative", "reasoning": "clear"}'
    result = _extract_json(raw)
    assert result["is_match"] is True
    assert result["match_strength"] == pytest.approx(0.9)


def test_extract_json_with_markdown_fence():
    raw = "```json\n{\"is_match\": false, \"match_strength\": 0.2, \"directional_impact\": 0, \"magnitude\": 0.1, \"news_type\": \"ambiguous\", \"reasoning\": \"not related\"}\n```"
    result = _extract_json(raw)
    assert result["is_match"] is False


def test_extract_json_no_json_raises():
    with pytest.raises(ValueError):
        _extract_json("There is no JSON here at all")


def test_verification_result_validates():
    data = {
        "is_match": True,
        "match_strength": 0.85,
        "directional_impact": 1,
        "magnitude": 0.6,
        "news_type": "quantitative",
        "reasoning": "Reports Tatum injury; relevant.",
    }
    result = VerificationResult(**data)
    assert result.is_match is True
    assert result.news_type == "quantitative"


def test_verification_result_rejects_invalid_news_type():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VerificationResult(
            is_match=True, match_strength=0.9,
            directional_impact=1, magnitude=0.5,
            news_type="bad_type", reasoning="x",
        )


def test_verification_result_rejects_out_of_range_strength():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VerificationResult(
            is_match=True, match_strength=1.5,
            directional_impact=0, magnitude=0.5,
            news_type="qualitative", reasoning="x",
        )


def test_verify_pair_success():
    """verify_pair returns a VerificationResult when the API returns valid JSON."""
    response_json = json.dumps({
        "is_match": True,
        "match_strength": 0.9,
        "directional_impact": 1,
        "magnitude": 0.8,
        "news_type": "high_attention",
        "reasoning": "Big game result.",
    })

    mock_content = MagicMock()
    mock_content.text = response_json
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    result = asyncio.run(verify_pair(
        client=mock_client,
        market_id="m1",
        market_question="Will the Chiefs win the Super Bowl?",
        article_id="a1",
        article_title="Chiefs defeat Eagles 38-35",
        article_lede="Kansas City wins a thriller.",
    ))

    assert result is not None
    assert result.is_match is True
    assert result.news_type == "high_attention"


def test_verify_pair_malformed_retries_and_returns_none():
    """verify_pair returns None after two malformed responses."""
    mock_content = MagicMock()
    mock_content.text = "not json at all"
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    result = asyncio.run(verify_pair(
        client=mock_client,
        market_id="m1",
        market_question="Will X happen?",
        article_id="a1",
        article_title="Irrelevant",
        article_lede=None,
    ))

    assert result is None
    # Should have been called exactly 2 times (original + 1 retry)
    assert mock_client.messages.create.call_count == 2
