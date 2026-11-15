"""Company registry (config/companies.yaml): pull_plan steps 1 and 2."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    ticker: str
    polymarket_tag_id: str
    wikipedia_title: str
    names: tuple[str, ...]  # plain name, short names, subsidiaries and brands; never tickers
    context_names: tuple[str, ...] = ()  # real brands that also mean something else; count only beside a `names` hit


def load_companies(path: str = "config/companies.yaml") -> list[Company]:
    raw = yaml.safe_load(Path(path).read_text())["companies"]
    out = [
        Company(
            id=r["id"], name=r["name"], ticker=r["ticker"],
            polymarket_tag_id=str(r["polymarket_tag_id"]),
            wikipedia_title=r["wikipedia_title"], names=tuple(r["names"]),
            context_names=tuple(r.get("context_names", ())),
        )
        for r in raw
    ]
    for field in ("id", "ticker", "polymarket_tag_id"):
        vals = [getattr(c, field) for c in out]
        if len(vals) != len(set(vals)):
            raise ValueError(f"duplicate {field} in {path}")
    return out
