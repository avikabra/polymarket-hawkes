import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.news.gdelt.bigquery import _HARD_CEILING_USD, _UNPARTITIONED_TABLE_RE, _check_budget
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
        assert a.body_text_available is False


def test_to_articles_schema_roundtrip(client):
    # Verifies Article objects serialize/deserialize cleanly (hawkes eligibility lives on NewsEvent)
    articles = client.to_articles(_fixture_df())
    for a in articles:
        dumped = a.model_dump()
        restored = Article(**dumped)
        assert restored.article_id == a.article_id
        assert restored.timestamp_precision == "day"


def _mock_client_with_cost(cost_usd: float) -> MagicMock:
    """A fake bigquery.Client whose dry-run query reports the given cost."""
    mock_client = MagicMock()
    mock_client.query.return_value.total_bytes_processed = cost_usd / 6.25 * 1e12
    return mock_client


_SAFE_SQL = "SELECT 1 FROM `gdelt-bq.gdeltv2.gkg_partitioned` WHERE _PARTITIONTIME >= '2024-01-01'"
_UNPARTITIONED_SQL = "SELECT 1 FROM `gdelt-bq.gdeltv2.gkg` WHERE DATE >= 20240101000000"


def test_check_budget_over_soft_budget_raises():
    mock_client = _mock_client_with_cost(6.0)
    with pytest.raises(RuntimeError, match="over the \\$5.00 budget"):
        _check_budget(mock_client, _SAFE_SQL, budget_usd=5.0)


def test_check_budget_under_soft_budget_passes():
    mock_client = _mock_client_with_cost(1.0)
    _check_budget(mock_client, _SAFE_SQL, budget_usd=5.0)  # must not raise


def test_check_budget_over_hard_ceiling_raises_even_with_higher_soft_budget():
    mock_client = _mock_client_with_cost(_HARD_CEILING_USD + 5)
    with pytest.raises(RuntimeError, match="hard ceiling"):
        _check_budget(mock_client, _SAFE_SQL, budget_usd=_HARD_CEILING_USD + 100)


def test_check_budget_unpartitioned_table_reference_raises():
    mock_client = _mock_client_with_cost(0.01)  # cheap, but wrong table
    with pytest.raises(RuntimeError, match="unpartitioned"):
        _check_budget(mock_client, _UNPARTITIONED_SQL, budget_usd=1000.0)


def test_check_budget_partitioned_table_not_falsely_flagged():
    mock_client = _mock_client_with_cost(0.01)
    _check_budget(mock_client, _SAFE_SQL, budget_usd=5.0)  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# A1: SQL-level stratified cap + content-farm exclude
# ─────────────────────────────────────────────────────────────────────────────

_ENTITY_FILTER = {
    "Apple": ["Apple"],
    "Microsoft": ["Microsoft"],
}


def _capture_query_sql(client_fixture, **kwargs) -> str:
    """Run pull_gkg_for_window against a fresh mock bq client, return the captured SQL."""
    mock_bq_client = MagicMock()
    # Cheap dry-run cost so _check_budget doesn't raise (comparing a bare
    # MagicMock to a float is always truthy and would falsely trip the ceiling).
    mock_bq_client.query.return_value.total_bytes_processed = 0.01 / 6.25 * 1e12
    mock_bq_client.query.return_value.to_dataframe.return_value = pd.DataFrame()
    client_fixture._bq = mock_bq_client
    # Bypass the real on-disk cache — never touch data/.cache/gdelt in a unit test.
    client_fixture._cache = MagicMock()
    client_fixture._cache.get.return_value = None
    client_fixture.pull_gkg_for_window("20240101", "20240131", _ENTITY_FILTER, **kwargs)
    # First .query() call is the dry-run budget check; second is the real query.
    calls = mock_bq_client.query.call_args_list
    assert len(calls) >= 2
    return calls[-1].args[0]


def test_pull_gkg_sql_contains_qualify_and_row_number(client):
    sql = _capture_query_sql(client)
    assert "QUALIFY" in sql
    assert "ROW_NUMBER" in sql


def test_pull_gkg_sql_contains_all_blocklist_domains(client):
    sql = _capture_query_sql(client)
    for domain in ["themarketsdaily", "dailypolitical", "tickerreport", "wkrb13", "modernreaders"]:
        assert domain in sql


def test_pull_gkg_sql_contains_is_not_null(client):
    sql = _capture_query_sql(client)
    assert "IS NOT NULL" in sql


def test_pull_gkg_sql_does_not_reference_unpartitioned_table(client):
    sql = _capture_query_sql(client)
    assert not _UNPARTITIONED_TABLE_RE.search(sql)


def test_pull_gkg_sql_references_partitioned_table(client):
    sql = _capture_query_sql(client)
    assert "gkg_partitioned" in sql


def test_pull_gkg_sql_caps_per_company_month_default(client):
    sql = _capture_query_sql(client)
    assert "<= 300" in sql  # _DEFAULT_CAP_PER_COMPANY_MONTH


def test_pull_gkg_sql_custom_cap(client):
    sql = _capture_query_sql(client, cap_per_company_month=50)
    assert "<= 50" in sql


def test_build_matched_company_case_sql_maps_canon_names():
    from src.news.gdelt.bigquery import _build_matched_company_case_sql
    sql = _build_matched_company_case_sql(_ENTITY_FILTER)
    assert "'''Apple'''" in sql
    assert "'''Microsoft'''" in sql
    assert "CASE" in sql
    assert "ELSE NULL" in sql


def test_build_matched_company_case_sql_empty_filter_raises():
    from src.news.gdelt.bigquery import _build_matched_company_case_sql
    with pytest.raises(ValueError):
        _build_matched_company_case_sql({})


def test_to_articles_includes_matched_company():
    df = _fixture_df()
    df["matched_company"] = ["Kansas City Chiefs", "Los Angeles Lakers", "NFL"]
    with patch("src.news.gdelt.bigquery.bigquery") as mock_bq:
        mock_bq.Client.return_value = MagicMock()
        from src.news.gdelt.bigquery import GDELTClient
        c = GDELTClient(project_id="test-project")
    articles = c.to_articles(df)
    metas = [json.loads(a.raw_metadata_json) for a in articles]
    assert [m["matched_company"] for m in metas] == ["Kansas City Chiefs", "Los Angeles Lakers", "NFL"]
