# GCP SETUP (one-time):
# 1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
# 2. Run: gcloud auth application-default login
# 3. Enable BigQuery API: gcloud services enable bigquery.googleapis.com --project=<your-project-id>
# 4. Set project_id in config/credentials.yaml (or config/ingest.yaml)
#
# Budget guard only. The query itself is built in src/ingest/gdelt_pull.py.
# Cost note: the BigQuery sandbox gives 1 TiB/month of free queries; the earlier
# 32-month scan of gkg_partitioned touched ~0.4 TB.

import re

from google.cloud import bigquery

# `gkg` is unpartitioned (INT64 DATE column, cannot prune) and scans the whole
# ~3.4 TB table. `gkg_partitioned` has the same schema plus a native
# _PARTITIONTIME column that DOES prune. Always use the latter.
TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"

# Soft default (overridable) vs. hard ceiling (never overridable).
# BigQuery on-demand pricing: $6.25/TiB.
DEFAULT_BUDGET_USD = 5.0
HARD_CEILING_USD = 25.0
_USD_PER_TIB = 6.25

# Matches `gdelt-bq.gdeltv2.gkg` as a whole table identifier, not as a prefix
# of `gdelt-bq.gdeltv2.gkg_partitioned` (no word boundary before the "_").
_UNPARTITIONED_TABLE_RE = re.compile(r"\bgdelt-bq\.gdeltv2\.gkg\b")


def check_schema(bq_client: "bigquery.Client", required: tuple[str, ...]) -> list[str]:
    """Zero-byte metadata call (tables.get, like `bq show --schema`).

    Returns the required column names missing from the table; raises if any are.
    Run this before any query is built.
    """
    have = {f.name.lower() for f in bq_client.get_table(TABLE).schema}
    missing = [c for c in required if c.lower() not in have]
    if missing:
        raise RuntimeError(f"{TABLE} is missing expected columns: {missing}")
    return missing


def dry_run_bytes(bq_client: "bigquery.Client", sql: str) -> int:
    """Bytes the query would process. Refuses the unpartitioned table first."""
    if _UNPARTITIONED_TABLE_RE.search(sql):
        raise RuntimeError(
            "query references the unpartitioned `gdelt-bq.gdeltv2.gkg` table — "
            "this scans the whole table (~3.4 TB); use gkg_partitioned instead"
        )
    dry = bq_client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    return int(dry.total_bytes_processed)


def cost_usd(n_bytes: int) -> float:
    return n_bytes / 2**40 * _USD_PER_TIB


def _check_budget(bq_client: "bigquery.Client", sql: str, budget_usd: float) -> int:
    """Raise if `sql` is unsafe to run: wrong table, or over budget/ceiling.
    Returns the dry-run bytes when the query is allowed."""
    n_bytes = dry_run_bytes(bq_client, sql)
    c = cost_usd(n_bytes)
    if c > HARD_CEILING_USD:
        raise RuntimeError(
            f"query would cost ${c:.2f}, over the ${HARD_CEILING_USD:.2f} "
            "hard ceiling — aborting (this ceiling cannot be overridden)"
        )
    if c > budget_usd:
        raise RuntimeError(f"query would cost ${c:.2f}, over the ${budget_usd:.2f} budget — aborting")
    return n_bytes


def run_guarded(bq_client: "bigquery.Client", sql: str, budget_usd: float = DEFAULT_BUDGET_USD):
    """Dry-run through the budget guard, then execute. Returns a DataFrame."""
    _check_budget(bq_client, sql, budget_usd)
    return bq_client.query(sql).to_dataframe()
