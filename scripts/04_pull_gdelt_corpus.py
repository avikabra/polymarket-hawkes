"""Script 04: Pull GDELT GKG corpus for the company-contract universe.

Entity filter is built from the companies ACTUALLY PRESENT in
data/polymarket/universe.parquet (script 01's output), not the full
COMPANY_DICT — companies with zero contracts are not worth paying to
scan for.

This script is recall-oriented: it emits CANDIDATE articles per company via a
name/ticker regex over GDELT's V2Persons/V2Organizations fields (reusing
company_filter.py's ambiguous-alias handling, e.g. dropping bare "ARM"/"Shell"
that would swamp counts with unrelated hits). It does not attempt to resolve
the ~5% ambiguous-name precision problem (e.g. "Meta", "Apple" as English
words) — precision is enforced downstream by FAISS candidate matching (08)
and LLM verification (09).

Cost note: queries `gdelt-bq.gdeltv2.gkg_partitioned` (partition-pruned on
_PARTITIONTIME) via GDELTClient, which also dry-runs and budget-checks the
query before executing — see src/news/gdelt/bigquery.py.

GDELT precision note: GDELT is day-precision only (bigquery.py hardcodes
timestamp_precision="day"), so 14_feasibility_gate.py's >=60% minute-precision
requirement will reject a GDELT-only corpus, and reaction_windows.py disables
the 1h/6h reaction windows for day-precision articles. This is a known,
accepted limitation of using GDELT as a source for now.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import json

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from dotenv import load_dotenv

from src.news.gdelt.bigquery import GDELTClient
from src.polymarket.company_filter import COMPANY_DICT, gdelt_entity_aliases
from src.utils import get_logger, write_scope

log = get_logger(__name__)

UNIVERSE_PATH = Path("data/polymarket/universe.parquet")


def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _universe_company_dict(universe_path: Path) -> dict[str, list[str]]:
    """COMPANY_DICT restricted to canonical names present in universe.parquet."""
    universe_ids = set(pd.read_parquet(universe_path)["company_id"].unique())
    return {
        canon: aliases
        for canon, aliases in COMPANY_DICT.items()
        if canon.lower().replace(" ", "_") in universe_ids
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-usd", type=float, default=5.0,
                    help="abort the BigQuery pull if its dry-run cost exceeds this "
                         "(soft; a non-overridable hard ceiling also applies, see bigquery.py)")
    args = ap.parse_args()

    load_dotenv()

    focal = _load_yaml("config/focal.yaml")["focal"]

    creds_path = Path("config/credentials.yaml")
    project_id = None
    if creds_path.exists():
        creds = _load_yaml(str(creds_path))
        project_id = creds.get("google_cloud", {}).get("project_id")

    if not project_id or project_id == "YOUR_GCP_PROJECT_ID":
        print("ERROR: GCP project_id not configured in config/credentials.yaml")
        print("Copy config/credentials.yaml.template → config/credentials.yaml and fill in your project ID.")
        sys.exit(1)

    if not UNIVERSE_PATH.exists():
        print(f"ERROR: {UNIVERSE_PATH} not found — run script 01 first.")
        sys.exit(1)

    company_dict = _universe_company_dict(UNIVERSE_PATH)
    if not company_dict:
        print("ERROR: no COMPANY_DICT entries match universe.parquet's company_ids.")
        sys.exit(1)
    company_ids = {canon.lower().replace(" ", "_") for canon in company_dict}
    entity_filter = sorted({
        alias
        for canon, aliases in company_dict.items()
        for alias in gdelt_entity_aliases(canon, aliases)
    })
    log.info("built entity filter", extra={"n_companies": len(company_dict), "n_aliases": len(entity_filter)})

    # focal.yaml uses ISO dates; GDELTClient expects YYYYMMDD
    start_date_iso = focal["discovery_start_date"]
    end_date_iso = focal["discovery_end_date"]
    start_date = start_date_iso.replace("-", "")
    end_date = end_date_iso.replace("-", "")

    try:
        client = GDELTClient(project_id=project_id)
    except Exception as exc:
        print(f"ERROR: Failed to initialize GCP client: {exc}")
        print("Ensure GOOGLE_APPLICATION_CREDENTIALS is set or run: gcloud auth application-default login")
        sys.exit(1)

    try:
        df = client.pull_gkg_for_window(start_date, end_date, entity_filter, budget_usd=args.budget_usd)
    except Exception as exc:
        print(f"ERROR: BigQuery query failed: {exc}")
        sys.exit(1)

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

    out_root.mkdir(parents=True, exist_ok=True)
    write_scope(out_root, company_ids, (start_date_iso, end_date_iso))
    success = out_root / "_SUCCESS"
    success.touch()
    log.info("done", extra={"months": len(months_written), "total_articles": len(articles)})


if __name__ == "__main__":
    main()
