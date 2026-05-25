import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.schemas import Article


def _fixture_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "GKGRECORDID": "20240801120000-1",
            "DATE": 20240801120000,
            "DocumentIdentifier": "https://espn.com/nfl/chiefs-game",
            "SourceCommonName": "ESPN",
            "V2Themes": "SPORTS;FOOTBALL_NFL",
            "V2Persons": "Patrick Mahomes,123;Andy Reid,456",
            "V2Organizations": "Kansas City Chiefs,789;NFL,234",
            "V2Locations": "",
            "V2Tone": "1.5,2.0,0.5,1.5,0.3,0.1,100",
            "SharingImage": "",
        },
        {
            "GKGRECORDID": "20240801130000-2",
            "DATE": 20240801130000,
            "DocumentIdentifier": "https://nba.com/lakers-update",
            "SourceCommonName": "NBA.com",
            "V2Themes": "SPORTS;BASKETBALL_NBA",
            "V2Persons": "LeBron James,10",
            "V2Organizations": "Los Angeles Lakers,50;NBA,80",
            "V2Locations": "",
            "V2Tone": "2.0,3.0,1.0,2.0,0.4,0.2,80",
            "SharingImage": "",
        },
        {
            "GKGRECORDID": "20240801140000-3",
            "DATE": 20240801140000,
            "DocumentIdentifier": "https://reuters.com/sports/nfl-season",
            "SourceCommonName": "Reuters",
            "V2Themes": "SPORTS;FOOTBALL_NFL;POLITICS",
            "V2Persons": "",
            "V2Organizations": "NFL,10",
            "V2Locations": "United States,1,US,,38,-97,US",
            "V2Tone": "0.5,1.0,0.5,0.5,0.2,0.1,120",
            "SharingImage": "https://reuters.com/img/nfl.jpg",
        },
    ])


@pytest.fixture
def client():
    with patch("src.news.gdelt.bigquery.bigquery") as mock_bq:
        mock_bq.Client.return_value = MagicMock()
        from src.news.gdelt.bigquery import GDELTClient
        return GDELTClient(project_id="test-project")


def test_to_articles_returns_3(client):
    articles = client.to_articles(_fixture_df())
    assert len(articles) == 3
    assert all(isinstance(a, Article) for a in articles)


def test_to_articles_timestamp_precision_and_published_at(client):
    articles = client.to_articles(_fixture_df())
    for a in articles:
        assert a.timestamp_precision == "day"
        assert a.published_at is None
        assert a.text_available is False


def test_to_articles_schema_roundtrip(client):
    # Verifies Article objects serialize/deserialize cleanly (hawkes eligibility lives on NewsEvent)
    articles = client.to_articles(_fixture_df())
    for a in articles:
        dumped = a.model_dump()
        restored = Article(**dumped)
        assert restored.article_id == a.article_id
        assert restored.timestamp_precision == "day"
