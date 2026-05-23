import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.polymarket.gamma import GammaClient

_FIXTURE = {
    "conditionId": "0xabc123",
    "slug": "test-market",
    "question": "Will the NBA Finals happen?",
    "description": "Test",
    "tags": [
        {"id": 1, "label": "nba", "slug": "nba"},
        {"id": 2, "label": "nba-finals", "slug": "nba-finals"},
    ],
    "startDate": "2024-08-01T00:00:00Z",
    "endDate": "2025-06-01T00:00:00Z",
    "resolutionDate": None,
    "clobTokenIds": '["0xtoken1", "0xtoken2"]',
    "volume": "100000.0",
    "outcomes": '["Yes", "No"]',
    "outcomePrices": '["0.5", "0.5"]',
    "winner": None,
    "active": False,
    "closed": True,
}


def test_parse_market_nba_finals_is_primary():
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    market = client.parse_market(_FIXTURE, category="nba")
    assert market.is_primary_sample is True
    assert market.market_type == "championship"


def test_parse_market_single_game_not_primary():
    raw = {**_FIXTURE, "tags": [{"id": 3, "label": "single-game", "slug": "single-game"}]}
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    market = client.parse_market(raw, category="nba")
    assert market.is_primary_sample is False
    assert market.market_type == "single_game"


def test_list_markets_returns_two_from_mock():
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    two_markets = [_FIXTURE, {**_FIXTURE, "conditionId": "0xdef456", "slug": "test-market-2"}]

    mock_resp = MagicMock()
    mock_resp.json.return_value = two_markets
    mock_resp.raise_for_status.return_value = None

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_resp)
    mock_async_ctx = MagicMock()
    mock_async_ctx.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_async_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_async_ctx):
        result = asyncio.get_event_loop().run_until_complete(client.list_markets(tag="nba"))

    assert len(result) == 2
