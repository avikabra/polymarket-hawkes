# GCP SETUP (one-time):
# 1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
# 2. Run: gcloud auth application-default login
# 3. Create a project: gcloud projects create <your-project-id>
# 4. Enable BigQuery API: gcloud services enable bigquery.googleapis.com --project=<your-project-id>
# 5. Set GOOGLE_APPLICATION_CREDENTIALS in .env to the path of your service account JSON, OR
#    use application-default credentials (gcloud auth login is sufficient for dev use)
# 6. Set project_id in config/credentials.yaml

import hashlib
import io
import json
import re
from datetime import datetime, timedelta

import pandas as pd
from google.cloud import bigquery

from src.schemas import Article
from src.utils import DiskCache, get_logger

# `gkg` is unpartitioned (INT64 DATE column, cannot prune) and scans the whole
# ~3.4 TB table regardless of date range. `gkg_partitioned` has the same schema
# plus a native _PARTITIONTIME column that DOES prune. Always use the latter —
# see scripts/audit_gdelt_company_coverage.py for the proven query shape.
_TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"
_COLS = (
    "GKGRECORDID, DATE, DocumentIdentifier, SourceCommonName, "
    "V2Themes, V2Persons, V2Organizations, V2Locations, V2Tone, SharingImage"
)

# Soft default (CLI-overridable via --budget-usd) vs. hard ceiling (never
# overridable — see _check_budget). BigQuery on-demand pricing: $6.25/TiB.
_DEFAULT_BUDGET_USD = 5.0
_HARD_CEILING_USD = 25.0
_USD_PER_TIB = 6.25

# Matches `gdelt-bq.gdeltv2.gkg` as a whole table identifier, not as a prefix
# of `gdelt-bq.gdeltv2.gkg_partitioned` (no word boundary before the "_").
_UNPARTITIONED_TABLE_RE = re.compile(r"\bgdelt-bq\.gdeltv2\.gkg\b")


def _check_budget(bq_client: "bigquery.Client", sql: str, budget_usd: float) -> None:
    """Raise if `sql` is unsafe to run: wrong table, or over budget/ceiling.

    All three checks raise (never warn): a reference to the unpartitioned
    `gdelt-bq.gdeltv2.gkg` table, a dry-run cost above the hard ceiling
    (regardless of `budget_usd`), and a dry-run cost above `budget_usd`.
    """
    if _UNPARTITIONED_TABLE_RE.search(sql):
        raise RuntimeError(
            "query references the unpartitioned `gdelt-bq.gdeltv2.gkg` table — "
            "this scans the whole table (~3.4 TB); use gkg_partitioned instead"
        )

    dry = bq_client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    cost_usd = dry.total_bytes_processed / 1e12 * _USD_PER_TIB

    if cost_usd > _HARD_CEILING_USD:
        raise RuntimeError(
            f"query would cost ${cost_usd:.2f}, over the ${_HARD_CEILING_USD:.2f} "
            "hard ceiling — aborting (this ceiling cannot be overridden)"
        )
    if cost_usd > budget_usd:
        raise RuntimeError(
            f"query would cost ${cost_usd:.2f}, over the ${budget_usd:.2f} budget — aborting"
        )


class GDELTClient:
    def __init__(self, project_id: str, cache_dir: str = "data/.cache/gdelt") -> None:
        self._bq = bigquery.Client(project=project_id)
        self._cache = DiskCache(cache_dir)
        self._log = get_logger(__name__)

    def pull_gkg_for_window(
        self,
        start_date: str,
        end_date: str,
        entity_filter: list[str],
        budget_usd: float = _DEFAULT_BUDGET_USD,
    ) -> pd.DataFrame:
        """Query GDELT GKG between start_date and end_date (YYYYMMDD inclusive)."""
        filter_hash = hashlib.sha256(
            "|".join(sorted(entity_filter)).encode()
        ).hexdigest()[:16]
        cache_key = f"gdelt:gkg:{start_date}:{end_date}:{filter_hash}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return pd.read_parquet(io.BytesIO(cached))

        # _PARTITIONTIME is a native TIMESTAMP partition column; compare as
        # ISO dates so BigQuery can prune (end is exclusive, start_date/end_date
        # are both inclusive calendar days).
        start_iso = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
        end_iso = (datetime.strptime(end_date, "%Y%m%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        # Triple-quoted regex literal: entity names can contain apostrophes
        # (e.g. "McDonald's"), which terminate a single-quoted SQL string.
        pattern = "|".join(re.escape(e) for e in entity_filter)
        sql = f"""
SELECT {_COLS}
FROM `{_TABLE}`
WHERE _PARTITIONTIME >= '{start_iso}'
  AND _PARTITIONTIME < '{end_iso}'
  AND REGEXP_CONTAINS(
      COALESCE(V2Persons, '') || ';' || COALESCE(V2Organizations, ''),
      r'''(?i)({pattern})'''
  )
"""
        _check_budget(self._bq, sql, budget_usd)
        self._log.info("running BigQuery query", extra={"start": start_date, "end": end_date})
        df = self._bq.query(sql).to_dataframe()
        self._log.info("query complete", extra={"rows": len(df)})

        buf = io.BytesIO()
        df.to_parquet(buf)
        self._cache.set(cache_key, buf.getvalue())
        return df

    def to_articles(self, df: pd.DataFrame) -> list[Article]:
        """Convert GKG DataFrame rows to Article stubs. Always timestamp_precision='day'."""
        articles = []
        for _, row in df.iterrows():
            url = str(row.get("DocumentIdentifier") or "")
            if not url:
                continue

            article_id = hashlib.sha256(url.encode()).hexdigest()
            source = str(row.get("SourceCommonName") or "")

            v2themes = str(row.get("V2Themes") or "")
            themes = [t.strip() for t in v2themes.split(";") if t.strip()]

            # V2Persons/V2Organizations format: "name,charoffset;name,charoffset;..."
            v2persons = str(row.get("V2Persons") or "")
            persons = [p.split(",")[0].strip() for p in v2persons.split(";") if "," in p]
            v2orgs = str(row.get("V2Organizations") or "")
            orgs = [o.split(",")[0].strip() for o in v2orgs.split(";") if "," in o]
            entities = list(dict.fromkeys(persons + orgs))

            raw_metadata = {
                "gkg_record_id": str(row.get("GKGRECORDID") or ""),
                "date_int": int(row.get("DATE") or 0),
                "v2tone": str(row.get("V2Tone") or ""),
                "v2locations": str(row.get("V2Locations") or ""),
                "sharing_image": str(row.get("SharingImage") or ""),
            }

            articles.append(Article(
                article_id=article_id,
                source=source,
                url=url,
                published_at=None,           # GDELT cannot provide minute-precision time
                timestamp_precision="day",   # HARD RULE — never change this for GDELT
                title=url,                   # placeholder; article_fetcher overwrites
                lede=None,
                body_text=None,
                body_text_available=False,
                entities=entities,
                themes=themes,
                raw_metadata_json=json.dumps(raw_metadata),
            ))
        return articles
