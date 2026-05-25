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

_TABLE = "gdelt-bq.gdeltv2.gkg"
_COLS = (
    "GKGRECORDID, DATE, DocumentIdentifier, SourceCommonName, "
    "V2Themes, V2Persons, V2Organizations, V2Locations, V2Tone, SharingImage"
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
    ) -> pd.DataFrame:
        """Query GDELT GKG between start_date and end_date (YYYYMMDD inclusive)."""
        filter_hash = hashlib.sha256(
            "|".join(sorted(entity_filter)).encode()
        ).hexdigest()[:16]
        cache_key = f"gdelt:gkg:{start_date}:{end_date}:{filter_hash}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return pd.read_parquet(io.BytesIO(cached))

        # DATE column is YYYYMMDDHHMMSS integer; filter as integers
        start_int = int(start_date) * 1_000_000
        end_dt = datetime.strptime(end_date, "%Y%m%d") + timedelta(days=1)
        end_int = int(end_dt.strftime("%Y%m%d")) * 1_000_000

        pattern = "|".join(re.escape(e) for e in entity_filter)
        sql = f"""
SELECT {_COLS}
FROM `{_TABLE}`
WHERE DATE >= {start_int}
  AND DATE < {end_int}
  AND REGEXP_CONTAINS(
      COALESCE(V2Persons, '') || ';' || COALESCE(V2Organizations, ''),
      r'(?i)({pattern})'
  )
"""
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
                text_available=False,
                entities=entities,
                themes=themes,
                raw_metadata_json=json.dumps(raw_metadata),
            ))
        return articles
