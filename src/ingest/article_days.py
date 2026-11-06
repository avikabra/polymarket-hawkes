"""Step 14: which company-days each article period covers.

Shock training period, 2022-01-01 to 2024-12-31: every day for every company. The GDELT pull
samples up to 50 articles per company per month from it.
Contract period, 2025-01-01 to 2026-10-31: the Eastern-time days on which a company has an
open contract that a live trader could already call liquid: a non-excluded rung, from the first
day its cumulative traded dollars through that day reach the floor (data/polymarket/daily_volume.parquet)
to its last day of trading. No outcome, lifetime or whole-life volume is read.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

TRAINING = (date(2022, 1, 1), date(2024, 12, 31))
CONTRACT = (date(2025, 1, 1), date(2026, 10, 31))


def union_ranges(ranges: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Merge inclusive day ranges that overlap or touch."""
    out: list[list[date]] = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1] + timedelta(days=1):
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(a, b) for a, b in out]


def contract_ranges(markets: pd.DataFrame, daily_volume: pd.DataFrame, min_dollars: float) -> pd.DataFrame:
    """One row per (company, merged range of open-contract days) inside the contract period.

    A non-excluded rung covers the days from max(its start day, the first day its cumulative
    dollars through that day reach `min_dollars`) to its last day of trading. That end is the
    actual end (the settlement time of a touched barrier), or the day before a stock split for
    a price rung opened before it.
    """
    k = markets[markets["excluded_reason"].isna()]
    hit = daily_volume[daily_volume["cum_dollars"] >= min_dollars]
    liquid_from = hit.groupby("condition_id")["day"].min()
    lo, hi = CONTRACT
    rows = []
    for cid, g in k.groupby("company_id"):
        spans = []
        for r in g.itertuples():
            if r.condition_id not in liquid_from.index:
                continue
            spans.append((max(r.start_et.date(), liquid_from[r.condition_id], lo), min(r.usable_end_et.date(), hi)))
        for s, e in union_ranges([sp for sp in spans if sp[0] <= sp[1]]):
            rows.append({"company_id": cid, "range_start": s, "range_end": e})
    return pd.DataFrame(rows, columns=["company_id", "range_start", "range_end"])


def range_days(ranges: pd.DataFrame) -> set[tuple[str, date]]:
    """Every (company, day) the ranges cover."""
    return {(r.company_id, d.date()) for r in ranges.itertuples() for d in pd.date_range(r.range_start, r.range_end)}


def days_to_ranges(days: set[tuple[str, date]]) -> pd.DataFrame:
    """Inverse of range_days: merge each company's days into inclusive ranges."""
    rows = []
    for cid in sorted({c for c, _ in days}):
        for s, e in union_ranges([(d, d) for c, d in days if c == cid]):
            rows.append({"company_id": cid, "range_start": s, "range_end": e})
    return pd.DataFrame(rows, columns=["company_id", "range_start", "range_end"])


def training_ranges(company_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{"company_id": c, "range_start": TRAINING[0], "range_end": TRAINING[1]}
                         for c in company_ids])


def split_by_month(ranges: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """{'YYYY-MM': ranges clipped to that month}, so each GDELT query scans one month."""
    out: dict[str, list[dict]] = {}
    for r in ranges.itertuples():
        m = pd.Timestamp(r.range_start).to_period("M")
        while m.start_time.date() <= r.range_end:
            s = max(r.range_start, m.start_time.date())
            e = min(r.range_end, m.end_time.date())
            out.setdefault(str(m), []).append({"company_id": r.company_id, "range_start": s, "range_end": e})
            m += 1
    return {k: pd.DataFrame(v) for k, v in sorted(out.items())}
