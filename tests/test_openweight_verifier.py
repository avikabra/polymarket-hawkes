"""Tests for src/matching/openweight_verifier.py using a mocked AsyncOpenAI client.

Hard constraint: this is the ONLY verification this module gets in this session —
never a real network call, and no local/hosted inference. See reports/llm_judge_deferred.md.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.matching.openweight_verifier import (
    VerificationResult,
    _extract_json,
    load_config,
    make_client,
    verify_pair_openweight,
)


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


def test_verify_pair_openweight_success():
    """verify_pair_openweight returns a VerificationResult when the server returns valid JSON."""
    response_json = json.dumps({
        "is_match": True,
        "match_strength": 0.9,
        "directional_impact": 1,
        "magnitude": 0.8,
        "news_type": "high_attention",
        "reasoning": "Big earnings beat.",
    })

    mock_message = MagicMock()
    mock_message.content = response_json
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = asyncio.run(verify_pair_openweight(
        client=mock_client,
        model="meta-llama/Llama-3.1-8B-Instruct",
        group_id="g1",
        group_text="Nvidia (NVDA) market_cap forecast for 2025-01: strikes [4000000000000.0]",
        article_id="a1",
        article_title="Nvidia beats Q4 earnings estimates",
        article_lede="Chip giant posts record revenue.",
    ))

    assert result is not None
    assert result.is_match is True
    assert result.news_type == "high_attention"
    mock_client.chat.completions.create.assert_called_once()


def test_verify_pair_openweight_malformed_retries_and_returns_none():
    """verify_pair_openweight returns None after two malformed responses."""
    mock_message = MagicMock()
    mock_message.content = "not json at all"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    result = asyncio.run(verify_pair_openweight(
        client=mock_client,
        model="test-model",
        group_id="g1",
        group_text="Will X happen?",
        article_id="a1",
        article_title="Irrelevant",
        article_lede=None,
    ))

    assert result is None
    assert mock_client.chat.completions.create.call_count == 2


def test_load_config_missing_file_raises_pointing_at_template(tmp_path, monkeypatch):
    missing_path = tmp_path / "openweight_llm.yaml"
    monkeypatch.setattr("src.matching.openweight_verifier.CONFIG_PATH", missing_path)
    with pytest.raises(RuntimeError, match="openweight_llm.yaml.template"):
        load_config()


def test_load_config_missing_keys_raises(tmp_path, monkeypatch):
    cfg_path = tmp_path / "openweight_llm.yaml"
    cfg_path.write_text("base_url: 'http://example.invalid/v1'\n")  # missing model, api_key_env_var
    monkeypatch.setattr("src.matching.openweight_verifier.CONFIG_PATH", cfg_path)
    with pytest.raises(RuntimeError):
        load_config()


def test_load_config_complete_returns_dict(tmp_path, monkeypatch):
    cfg_path = tmp_path / "openweight_llm.yaml"
    cfg_path.write_text(
        "base_url: 'http://example.invalid/v1'\n"
        "model: 'test-model'\n"
        "api_key_env_var: 'TEST_OPENWEIGHT_KEY'\n"
    )
    monkeypatch.setattr("src.matching.openweight_verifier.CONFIG_PATH", cfg_path)
    cfg = load_config()
    assert cfg["base_url"] == "http://example.invalid/v1"
    assert cfg["model"] == "test-model"


def test_make_client_no_default_base_url_missing_key_raises(monkeypatch):
    monkeypatch.delenv("TEST_OPENWEIGHT_KEY_UNSET", raising=False)
    cfg = {
        "base_url": "http://example.invalid/v1",
        "model": "test-model",
        "api_key_env_var": "TEST_OPENWEIGHT_KEY_UNSET",
    }
    with pytest.raises(RuntimeError, match="TEST_OPENWEIGHT_KEY_UNSET"):
        make_client(cfg)


def test_make_client_builds_async_openai_with_configured_base_url(monkeypatch):
    monkeypatch.setenv("TEST_OPENWEIGHT_KEY_SET", "dummy-token")
    cfg = {
        "base_url": "http://example.invalid/v1",
        "model": "test-model",
        "api_key_env_var": "TEST_OPENWEIGHT_KEY_SET",
    }
    client = make_client(cfg)
    assert str(client.base_url).startswith("http://example.invalid/v1")
