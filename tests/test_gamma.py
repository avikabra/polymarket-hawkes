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


def test_parse_market_single_game_is_primary():
    # single_game is a primary type in config/focal.yaml; "games" is the real
    # tag slug the live /events endpoint emits for single-game markets.
    raw = {**_FIXTURE, "tags": [{"id": 3, "label": "games", "slug": "games"}]}
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    market = client.parse_market(raw, category="nba")
    assert market.is_primary_sample is True
    assert market.market_type == "single_game"


def test_parse_market_resolution_from_outcome_prices():
    # /events never populates `winner`; resolution comes from outcomePrices.
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    yes = client.parse_market({**_FIXTURE, "outcomePrices": '["1", "0"]'}, category="nba")
    no = client.parse_market({**_FIXTURE, "outcomePrices": '["0", "1"]'}, category="nba")
    assert yes.resolved_outcome == "YES"
    assert no.resolved_outcome == "NO"


def test_list_markets_flattens_events_and_inherits_tags():
    # list_markets now queries /events (nested markets inherit event tags) after
    # resolving the tag slug to a numeric tag_id.
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    event_tags = [{"id": 1, "label": "nba", "slug": "nba"}]
    events_page = [
        {
            "slug": "evt-1",
            "tags": event_tags,
            "markets": [
                {**_FIXTURE, "tags": None},
                {**_FIXTURE, "conditionId": "0xdef456", "slug": "test-market-2", "tags": None},
            ],
        }
    ]

    async def fake_get(path, params):
        if path.startswith("/tags/slug/"):
            return {"id": "745"}
        return events_page

    with patch.object(client, "_get", AsyncMock(side_effect=fake_get)):
        result = asyncio.run(client.list_markets(tag="nba"))

    assert len(result) == 2
    assert result[0]["tags"] == event_tags  # inherited from parent event
