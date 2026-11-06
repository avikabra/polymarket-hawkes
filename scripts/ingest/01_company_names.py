"""Step 2: draft each company's subsidiary and brand names from Wikidata.

Resolves each company's Wikipedia page to its Wikidata item and lists the items it records as
subsidiaries (P355) and brands (P1716). Writes data/ingest/company_names_draft.csv for a
one-time review; reviewed names go into the `names` list in config/companies.yaml. A name that
belongs to another study company stays with that company only and is flagged here.

    uv run python scripts/ingest/01_company_names.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import time

import httpx
import yaml

from src.ingest.companies import load_companies

_API = "https://www.wikidata.org/w/api.php"
_SPARQL = "https://query.wikidata.org/sparql"
_OUT = Path("data/ingest/company_names_draft.csv")


def _headers() -> dict:
    # Wikimedia rejects bare agent strings (403); it wants a descriptive agent with a contact
    contact = (yaml.safe_load(open("config/ingest.yaml")).get("contact") or "").strip()
    if not contact:
        sys.exit("set `contact` in config/ingest.yaml (project URL) for the Wikimedia User-Agent")
    return {"User-Agent": f"thesis-polymarket-registry/0.1 ({contact}; academic research) httpx"}


def qid_for_title(client: httpx.Client, title: str) -> str | None:
    r = client.get(_API, params={"action": "wbgetentities", "sites": "enwiki", "titles": title,
                                 "props": "info", "format": "json"})
    r.raise_for_status()
    return next((q for q in r.json().get("entities", {}) if q.startswith("Q")), None)


def related(client: httpx.Client, qid: str) -> list[tuple[str, str, str]]:
    q = f"""SELECT ?rel ?item ?itemLabel WHERE {{
      {{ wd:{qid} wdt:P355 ?item . BIND("subsidiary" AS ?rel) }}
      UNION {{ wd:{qid} wdt:P1716 ?item . BIND("brand" AS ?rel) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}"""
    r = client.get(_SPARQL, params={"query": q, "format": "json"})
    r.raise_for_status()
    return [(b["rel"]["value"], b["item"]["value"].rsplit("/", 1)[-1], b["itemLabel"]["value"])
            for b in r.json()["results"]["bindings"]]


def main() -> None:
    companies = load_companies()
    owner = {n: c.id for c in companies for n in (c.name, *c.names)}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60.0, headers=_headers()) as client, _OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_id", "relation", "wikidata_id", "label", "in_names", "other_study_company"])
        for c in companies:
            qid = qid_for_title(client, c.wikipedia_title)
            if qid is None:
                print(f"no Wikidata item for {c.id} ({c.wikipedia_title})")
                continue
            for rel, item, label in related(client, qid):
                other = owner.get(label)
                w.writerow([c.id, rel, item, label, label in c.names,
                            other if other and other != c.id else ""])
            time.sleep(1.0)
    print(f"wrote {_OUT}")


if __name__ == "__main__":
    main()
