import asyncio
from unittest.mock import patch

from src.news.feeds.nba_stats import NBAStatsFetcher
from src.news.feeds.rss import RSSFetcher
from src.schemas import Article

_RSS_WITH_TIME = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article With Time</title>
      <link>https://example.com/article-1</link>
      <pubDate>Thu, 01 Aug 2024 12:30:00 +0000</pubDate>
      <description>Test description text.</description>
    </item>
  </channel>
</rss>"""

_RSS_NO_TIME = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article No Date</title>
      <link>https://example.com/article-2</link>
      <description>No date here.</description>
    </item>
  </channel>
</rss>"""

_NBA_MOCK = {
    "resultSets": [{
        "name": "LeagueGameLog",
        "headers": [
            "SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME",
            "GAME_ID", "GAME_DATE", "MATCHUP", "WL", "PTS",
        ],
        "rowSet": [
            ["42400", 1610612747, "LAL", "Los Angeles Lakers",
             "0042400315", "2024-08-01", "LAL vs. BOS", "W", 112],
            ["42400", 1610612738, "BOS", "Boston Celtics",
             "0042400315", "2024-08-01", "BOS @ LAL", "L", 98],
        ],
    }],
}


def test_rss_minute_precision():
    with patch("src.news.feeds.rss.DiskCache") as mock_cls:
        mock_cls.return_value.get.return_value = _RSS_WITH_TIME
        articles = asyncio.run(RSSFetcher().fetch("https://example.com/feed", "test"))
    assert len(articles) == 1
    assert articles[0].timestamp_precision == "minute"
    assert articles[0].published_at is not None


def test_rss_day_precision_no_date():
    with patch("src.news.feeds.rss.DiskCache") as mock_cls:
        mock_cls.return_value.get.return_value = _RSS_NO_TIME
        articles = asyncio.run(RSSFetcher().fetch("https://example.com/feed", "test"))
    assert len(articles) == 1
    assert articles[0].timestamp_precision == "day"
    assert articles[0].published_at is None


def test_nba_stats_day_precision():
    with patch("src.news.feeds.nba_stats.DiskCache"):
        fetcher = NBAStatsFetcher()
    articles = fetcher._rows_to_articles(_NBA_MOCK)
    assert len(articles) == 1
    assert articles[0].timestamp_precision == "day"
    assert isinstance(articles[0], Article)
