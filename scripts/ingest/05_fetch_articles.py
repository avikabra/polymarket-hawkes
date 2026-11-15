"""Steps 17 and 18: fetch article text and recheck names, one chunk at a time.

Each task handles the URLs whose stable hash falls in its part, so --parts tasks run in
parallel (scripts/bouchet/ingest_05_fetch.sbatch runs 4). Fetching resumes from the shards
already written. Each shard keeps text only for articles whose extracted text names a candidate
company; 08_map_companies.py reads those shards directly. Per-chunk counts print as JSON lines.

    uv run python scripts/ingest/05_fetch_articles.py --limit 200   # trial
    uv run python scripts/ingest/05_fetch_articles.py --part 0 --parts 4
"""
from __future__ import annotations

import argparse
import faulthandler
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml

from src.ingest.body_fetch import run
from src.ingest.companies import load_companies
from src.ingest.gdelt_pull import load_candidates


def main() -> None:
    faulthandler.enable()  # a native crash in this process prints the Python traceback
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="data/news/gdelt_candidates")
    ap.add_argument("--fetched", default="data/news/fetched")
    ap.add_argument("--limit", type=int, default=None, help="max URLs to fetch this run")
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--parts", type=int, default=1)
    args = ap.parse_args()
    if not 0 <= args.part < args.parts:
        sys.exit("--part must be in [0, --parts)")

    cfg = yaml.safe_load(open("config/ingest.yaml"))["body_fetch"]
    cands = load_candidates(args.candidates)
    names = {c.id: c.names for c in load_companies()}
    n = run(cands, names, args.fetched, contact=cfg["contact"],
            global_concurrency=cfg["global_concurrency"],
            per_domain_concurrency=cfg["per_domain_concurrency"],
            timeout_s=cfg["timeout_s"], chunk_size=cfg["chunk_size"],
            parse_workers=cfg["parse_workers"], parse_timeout_s=cfg["parse_timeout_s"],
            max_html_bytes=cfg["max_html_bytes"],
            part=args.part, parts=args.parts, limit=args.limit)
    print(f"part {args.part}/{args.parts}: fetched {n} URLs -> {args.fetched}")


if __name__ == "__main__":
    main()
