"""Script 04: Pull GDELT GKG corpus for focal NFL/NBA markets."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.news.gdelt.bigquery import GDELTClient
from src.utils import get_logger

log = get_logger(__name__)

_NFL_TERMS = [
    "NFL", "National Football League", "Super Bowl",
    "Kansas City Chiefs", "Philadelphia Eagles", "San Francisco 49ers",
    "Dallas Cowboys", "New England Patriots", "Buffalo Bills",
    "Miami Dolphins", "Baltimore Ravens", "Cincinnati Bengals",
    "Cleveland Browns", "Pittsburgh Steelers", "Houston Texans",
    "Indianapolis Colts", "Jacksonville Jaguars", "Tennessee Titans",
    "Denver Broncos", "Las Vegas Raiders", "Los Angeles Chargers",
    "New York Giants", "New York Jets", "Washington Commanders",
    "Chicago Bears", "Detroit Lions", "Green Bay Packers",
    "Minnesota Vikings", "Atlanta Falcons", "Carolina Panthers",
    "New Orleans Saints", "Tampa Bay Buccaneers",
    "Patrick Mahomes", "Josh Allen", "Jalen Hurts",
]

_NBA_TERMS = [
    "NBA", "National Basketball Association", "NBA Finals",
    "Los Angeles Lakers", "Boston Celtics", "Golden State Warriors",
    "Milwaukee Bucks", "Miami Heat", "Denver Nuggets",
    "Phoenix Suns", "Dallas Mavericks", "Oklahoma City Thunder",
    "Sacramento Kings", "Minnesota Timberwolves", "New Orleans Pelicans",
    "Memphis Grizzlies", "New York Knicks", "Brooklyn Nets",
    "Philadelphia 76ers", "Toronto Raptors", "Chicago Bulls",
    "Atlanta Hawks", "Charlotte Hornets", "Washington Wizards",
    "Cleveland Cavaliers", "Detroit Pistons", "Indiana Pacers",
    "San Antonio Spurs", "Houston Rockets", "Portland Trail Blazers",
    "Utah Jazz", "Los Angeles Clippers",
    "LeBron James", "Stephen Curry", "Nikola Jokic",
]

_TERMS_BY_CATEGORY = {"nfl": _NFL_TERMS, "nba": _NBA_TERMS}


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    focal = _load_yaml("config/focal.yaml")["focal"]

    creds_path = Path("config/credentials.yaml")
    project_id = None
    if creds_path.exists():
        creds = _load_yaml(str(creds_path))
        project_id = creds.get("google_cloud", {}).get("project_id")

    if not project_id or project_id == "YOUR_GCP_PROJECT_ID":
        print("ERROR: GCP project_id not configured in config/credentials.yaml")
        print("Copy config/credentials.yaml.template → config/credentials.yaml and fill in your project ID.")
        return

    categories = focal["categories"]
    entity_filter: list[str] = []
    for cat in categories:
        entity_filter.extend(_TERMS_BY_CATEGORY.get(cat, []))
    entity_filter = list(dict.fromkeys(entity_filter))

    # focal.yaml uses ISO dates; GDELTClient expects YYYYMMDD
    start_date = focal["start_date"].replace("-", "")
    end_date = focal["end_date"].replace("-", "")

    try:
        client = GDELTClient(project_id=project_id)
    except Exception as exc:
        print(f"ERROR: Failed to initialize GCP client: {exc}")
        print("Ensure GOOGLE_APPLICATION_CREDENTIALS is set or run: gcloud auth application-default login")
        return

    try:
        df = client.pull_gkg_for_window(start_date, end_date, entity_filter)
    except Exception as exc:
        print(f"ERROR: BigQuery query failed: {exc}")
        return

    articles = client.to_articles(df)

    # Group by year-month from DATE integer (YYYYMMDDHHMMSS → first 6 digits = YYYYMM)
    out_root = Path("data/news/gdelt_gkg")
    months_written: set[str] = set()
    month_groups: dict[str, list] = {}
    for a in articles:
        raw_meta = json.loads(a.raw_metadata_json)
        date_int = raw_meta.get("date_int", 0)
        yyyymm = str(date_int)[:6]
        month_groups.setdefault(yyyymm, []).append(a.model_dump())

    for yyyymm, records in month_groups.items():
        year, month = int(yyyymm[:4]), int(yyyymm[4:6])
        out_path = out_root / f"year={year}/month={month:02d}/part-{yyyymm}.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(pd.DataFrame(records)), out_path)
        months_written.add(yyyymm)

    unique_domains = len({a.source for a in articles})
    print(f"\nMonths pulled: {len(months_written)}")
    print(f"Total articles: {len(articles)}")
    print(f"Unique domains: {unique_domains}")

    success = out_root / "_SUCCESS"
    out_root.mkdir(parents=True, exist_ok=True)
    success.touch()
    log.info("done", extra={"months": len(months_written), "total_articles": len(articles)})


if __name__ == "__main__":
    main()
