import asyncio
from unittest.mock import AsyncMock, patch

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


def test_parse_market_no_classification_is_other():
    # Without a classification, contract_family defaults to "other" and is_primary_sample is False.
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    market = client.parse_market(_FIXTURE, category="nba")
    assert market.contract_family == "other"
    assert market.is_primary_sample is False


def test_parse_market_price_ladder_classification():
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    classification = {
        "contract_family": "price_ladder",
        "ladder_metric": "price",
        "company_name": "Nvidia",
        "ticker": "NVDA",
        "company_id": "nvidia",
    }
    strike_fields = {
        "strike_price": 190.0,
        "strike_direction": "above",
        "price_expiry_month": "2024-06",
    }
    market = client.parse_market(
        _FIXTURE,
        classification=classification,
        strike_fields=strike_fields,
    )
    assert market.contract_family == "price_ladder"
    assert market.is_primary_sample is True
    assert market.company_name == "Nvidia"
    assert market.ticker == "NVDA"
    assert market.company_id == "nvidia"
    assert market.strike_price == 190.0
    assert market.strike_direction == "above"
    assert market.price_expiry_month == "2024-06"
    assert market.category == "price_ladder"


def test_parse_market_valuation_ladder_is_primary():
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    classification = {
        "contract_family": "valuation_ladder",
        "ladder_metric": "valuation",
        "company_name": "Stripe",
        "ticker": None,
        "company_id": "stripe",
    }
    strike_fields = {
        "strike_price": 100e9,
        "strike_direction": "above",
        "price_expiry_month": "2025-03",
    }
    market = client.parse_market(
        _FIXTURE,
        classification=classification,
        strike_fields=strike_fields,
    )
    assert market.contract_family == "valuation_ladder"
    assert market.is_primary_sample is True
    assert market.category == "valuation_ladder"


def test_parse_market_corporate_event_is_primary():
    client = GammaClient(cache_dir="/tmp/test_gamma_cache")
    classification = {
        "contract_family": "corporate_event",
        "company_name": "Apple",
        "ticker": "AAPL",
        "company_id": "apple",
    }
    market = client.parse_market(_FIXTURE, classification=classification)
    assert market.contract_family == "corporate_event"
    assert market.is_primary_sample is True


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
