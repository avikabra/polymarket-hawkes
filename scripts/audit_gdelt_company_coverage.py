"""GDELT coverage audit for the company-contract universe (Weeks 7-9).

Answers Kelly's data-review question "do we have news coverage for these
contracts?" along four axes: article volume per company-month, source breadth,
timestamp quality, and metadata richness.

Cost note: queries `gdelt-bq.gdeltv2.gkg_partitioned` (partition-pruned on
_PARTITIONTIME), NOT `gdelt-bq.gdeltv2.gkg`.  The unpartitioned table cannot
prune on its INT64 `DATE` column and scans ~3.4 TB per day of window.

Outputs
    data/news/audit/gdelt_company_month.parquet   article counts per company-month
    data/news/audit/gdelt_source_mix.parquet      top domains for the matched corpus
    data/news/audit/gdelt_metadata_sample.parquet 1-month full-column sample
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import re

import yaml
from dotenv import load_dotenv
from google.cloud import bigquery

from src.polymarket.company_filter import COMPANY_DICT
from src.utils import get_logger

log = get_logger(__name__)

_TABLE = "`gdelt-bq.gdeltv2.gkg_partitioned`"
_OUT = Path("data/news/audit")

# Aliases that are ordinary English words or shadow unrelated organisations.
# Kept in the universe classifier (where the question text disambiguates) but
# excluded from the GDELT entity regex, where they would swamp the counts.
_AMBIGUOUS = {
    "ARM", "Block", "Block Inc", "Square", "Shell", "Visa", "Intel",
    "Lucid", "AMC", "Coke", "Citi", "Amex",
}


def _entity_aliases(canon: str, aliases: list[str]) -> list[str]:
    """Name-like aliases only: drop bare tickers and ambiguous common words."""
    out = [
        a for a in aliases
        if not (a.isupper() and 2 <= len(a) <= 5) and a not in _AMBIGUOUS
    ]
    return out or ([canon] if canon not in _AMBIGUOUS else [])


def _build_patterns() -> dict[str, str]:
    pats: dict[str, str] = {}
    for canon, aliases in COMPANY_DICT.items():
        names = _entity_aliases(canon, aliases)
        if not names:
            continue
        alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        pats[canon] = f"(?i)({alt})"
    return pats


def _struct_array(pats: dict[str, str]) -> str:
    # Triple-quoted literals: company names contain apostrophes (McDonald's),
    # which terminate a single-quoted SQL string.
    rows = [f"STRUCT('''{c}''' AS canon, r'''{p}''' AS pat)" for c, p in pats.items()]
    return "[\n    " + ",\n    ".join(rows) + "\n  ]"


def _combined(pats: dict[str, str]) -> str:
    inner = "|".join(p[len("(?i)("):-1] for p in pats.values())
    return f"(?i)({inner})"


def _run(client: bigquery.Client, label: str, sql: str, budget_usd: float):
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    cost = dry.total_bytes_processed / 1e12 * 6.25
    print(f"[{label}] scans {dry.total_bytes_processed/1e9:8.2f} GB  ~${cost:.3f}")
    if cost > budget_usd:
        raise RuntimeError(f"{label} would cost ${cost:.2f}, over the ${budget_usd:.2f} budget — aborting")
    return client.query(sql).to_dataframe()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--end", default="2026-08-29")
    ap.add_argument("--sample-month-start", default="2026-08-01")
    ap.add_argument("--sample-month-end", default="2026-09-01")
    ap.add_argument("--budget-usd", type=float, default=4.0,
                    help="abort any single query whose dry run exceeds this")
    args = ap.parse_args()

    load_dotenv()
    pid = (yaml.safe_load(Path("config/credentials.yaml").read_text())
           .get("google_cloud", {}).get("project_id"))
    if not pid or pid == "YOUR_GCP_PROJECT_ID":
        raise RuntimeError("GCP project_id not configured in config/credentials.yaml")
    client = bigquery.Client(project=pid)

    pats = _build_patterns()
    log.info("built entity patterns", extra={"n_companies": len(pats)})
    combined, struct = _combined(pats), _struct_array(pats)
    window = f"_PARTITIONTIME >= '{args.start}' AND _PARTITIONTIME < '{args.end}'"
    ents = "COALESCE(V2Organizations,'') || ';' || COALESCE(V2Persons,'')"

    _OUT.mkdir(parents=True, exist_ok=True)

    # ── 1. article volume per company-month ──────────────────────────────────
    by_month = _run(client, "company-month", f"""
WITH hits AS (
  SELECT _PARTITIONTIME AS pt, DocumentIdentifier, SourceCommonName, {ents} AS ents
  FROM {_TABLE}
  WHERE {window} AND REGEXP_CONTAINS({ents}, r'''{combined}''')
)
SELECT c.canon AS company,
       FORMAT_TIMESTAMP('%Y-%m', h.pt) AS month,
       COUNT(*) AS n_records,
       COUNT(DISTINCT h.DocumentIdentifier) AS n_urls,
       COUNT(DISTINCT h.SourceCommonName) AS n_sources,
       COUNT(DISTINCT DATE(h.pt)) AS n_days_covered
FROM hits h, UNNEST({struct}) c
WHERE REGEXP_CONTAINS(h.ents, c.pat)
GROUP BY company, month
ORDER BY company, month
""", args.budget_usd)
    by_month.to_parquet(_OUT / "gdelt_company_month.parquet", index=False)
    log.info("wrote company-month coverage", extra={"rows": len(by_month)})

    # ── 2. source mix (which domains carry this corpus) ──────────────────────
    sources = _run(client, "source-mix", f"""
SELECT SourceCommonName AS source,
       COUNT(*) AS n_records,
       COUNT(DISTINCT DocumentIdentifier) AS n_urls
FROM {_TABLE}
WHERE {window} AND REGEXP_CONTAINS({ents}, r'''{combined}''')
GROUP BY source
ORDER BY n_records DESC
LIMIT 400
""", args.budget_usd)
    sources.to_parquet(_OUT / "gdelt_source_mix.parquet", index=False)
    log.info("wrote source mix", extra={"rows": len(sources)})

    # ── 3. one-month full-column sample for metadata / timestamp assessment ──
    sample = _run(client, "metadata-sample", f"""
SELECT GKGRECORDID, DATE, _PARTITIONTIME AS partition_time, DocumentIdentifier,
       SourceCommonName, V2Themes, V2Persons, V2Organizations, V2Locations, V2Tone
FROM {_TABLE}
WHERE _PARTITIONTIME >= '{args.sample_month_start}'
  AND _PARTITIONTIME < '{args.sample_month_end}'
  AND REGEXP_CONTAINS({ents}, r'''{combined}''')
""", args.budget_usd)
    sample.to_parquet(_OUT / "gdelt_metadata_sample.parquet", index=False)
    log.info("wrote metadata sample", extra={"rows": len(sample)})

    if by_month.empty:
        raise RuntimeError("company-month coverage is empty — entity regex or window is wrong")

    print(f"\ncompanies with any coverage : {by_month['company'].nunique()} / {len(pats)}")
    print(f"months covered              : {by_month['month'].nunique()}")
    print(f"total matched GKG records   : {int(by_month['n_records'].sum()):,}")
    print(f"metadata sample rows        : {len(sample):,}")


if __name__ == "__main__":
    main()
