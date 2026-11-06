"""Step 20: download each company's whole English Wikipedia page as plain text.

Writes data/news/company_pages.parquet (company_id, wikipedia_title, revision_id, text).

    uv run python scripts/ingest/06_pull_wikipedia.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import time

import httpx
import pandas as pd
import yaml

from src.ingest.companies import load_companies

_API = "https://en.wikipedia.org/w/api.php"
_OUT = Path("data/news/company_pages.parquet")


def _headers() -> dict:
    # Wikimedia rejects bare agent strings (403); it wants a descriptive agent with a contact
    contact = (yaml.safe_load(open("config/ingest.yaml")).get("contact") or "").strip()
    if not contact:
        sys.exit("set `contact` in config/ingest.yaml (project URL) for the Wikimedia User-Agent")
    return {"User-Agent": f"thesis-polymarket-registry/0.1 ({contact}; academic research) httpx"}


def page_text(client: httpx.Client, title: str) -> tuple[int, str]:
    r = client.get(_API, params={"action": "query", "prop": "extracts|revisions", "explaintext": 1,
                                 "rvprop": "ids", "redirects": 1, "titles": title,
                                 "format": "json", "formatversion": 2})
    r.raise_for_status()
    page = r.json()["query"]["pages"][0]
    if page.get("missing") or not page.get("extract"):
        raise RuntimeError(f"no Wikipedia text for {title!r}")
    return page["revisions"][0]["revid"], page["extract"]


def main() -> None:
    rows = []
    with httpx.Client(timeout=60.0, headers=_headers()) as client:
        for c in load_companies():
            rev, text = page_text(client, c.wikipedia_title)
            rows.append({"company_id": c.id, "wikipedia_title": c.wikipedia_title,
                         "revision_id": rev, "text": text})
            time.sleep(0.5)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_parquet(_OUT, index=False)
    print(f"{len(df)} pages, median {int(df['text'].str.split().str.len().median())} words -> {_OUT}")


if __name__ == "__main__":
    main()
