"""Steps 14 to 16: pull GDELT candidate articles for one month of one article period.

Reads GDELT's free public GKG 2.1 files (no Google account), one zip at a time into memory.
A training month already written is skipped, so a stopped run resumes; a month with failed
downloads is not written. Missing files (404) are normal and are listed in <out>/_logs.

A contract month can be rerun after the contract ranges change. The days scanned so far are
recorded in <out>/_scanned; a rerun scans only the days not yet recorded, prints them, and adds
their rows to the month file. Existing rows stay (a url already present for a company is not
added again). A month written before this record existed has none, so its first rerun scans every
day and keeps the old rows. A month with no ranges exits 0 without writing.

    uv run python scripts/ingest/04_pull_gdelt.py --month 2022-01 --period training
    uv run python scripts/ingest/04_pull_gdelt.py --month 2025-01 --period contract

On Bouchet, scripts/bouchet/ingest_04_gdelt.sbatch runs every month as a Slurm array.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import yaml

from src.ingest.article_days import (
    contract_ranges, days_to_ranges, range_days, split_by_month, training_ranges,
)
from src.ingest.companies import load_companies
from src.ingest.gdelt_pull import pull_month, write_month


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--period", required=True, choices=["training", "contract"])
    ap.add_argument("--markets", default="data/polymarket/contracts/markets.parquet")
    ap.add_argument("--out", default="data/news/gdelt_candidates")
    ap.add_argument("--workers", type=int, default=4, help="concurrent downloads")
    args = ap.parse_args()

    out = Path(args.out) / f"period={args.period}" / f"month={args.month}.parquet"
    scanned_path = Path(args.out) / "_scanned" / f"{args.period}_{args.month}.parquet"
    if out.exists() and args.period == "training":
        print(f"{args.period} {args.month}: already written, skipping")
        return

    cfg = yaml.safe_load(open("config/ingest.yaml"))
    companies = load_companies()
    names = {c.id: c.names for c in companies}
    if args.period == "training":
        by_month = split_by_month(training_ranges([c.id for c in companies]))
        sample = cfg["gdelt"]["sample_per_company_month"]
        only_days = tuple(cfg["gdelt"]["training_days"])
    else:
        ccfg = yaml.safe_load(open("config/contracts.yaml"))
        ranges = contract_ranges(pd.read_parquet(args.markets), pd.read_parquet(ccfg["paths"]["daily_volume"]),
                                 ccfg["liquidity"]["liquid_1k"])
        by_month = split_by_month(ranges)
        sample = only_days = None
    if args.month not in by_month:
        print(f"{args.period} {args.month}: no ranges (outside the period or no liquid open contracts), nothing to do")
        return
    ranges = by_month[args.month]

    old = None
    if args.period == "contract":
        want = range_days(ranges)
        done = set(map(tuple, pd.read_parquet(scanned_path)[["company_id", "day"]].itertuples(index=False))) \
            if out.exists() and scanned_path.exists() else set()
        new = want - done
        if out.exists() and not new:
            print(f"{args.period} {args.month}: no new days, skipping")
            return
        if out.exists():
            old = pd.read_parquet(out)
            note = "" if done else " (no scan record for this month: every day is rescanned, old rows are kept)"
            print(f"{args.period} {args.month}: {len(new)} new company-days{note}")
            for cid, g in sorted({c: sorted(d for c2, d in new if c2 == c) for c, _ in new}.items()):
                print(f"  new {cid}: {g[0]} .. {g[-1]} ({len(g)} days)" if len(g) > 1 else f"  new {cid}: {g[0]}")
        ranges = days_to_ranges(new)

    df, stats, missing, failed = pull_month(args.month, ranges, names, sample, args.workers,
                                            cfg.get("contact") or "", only_days)
    logs = Path(args.out) / "_logs"
    logs.mkdir(parents=True, exist_ok=True)
    stem = f"{args.period}_{args.month}"
    (logs / f"{stem}_missing.txt").write_text("".join(u + "\n" for u in missing))
    (logs / f"{stem}_failed.txt").write_text("".join(f + "\n" for f in failed))
    print(f"{args.period} {args.month}: {ranges['company_id'].nunique()} companies, "
          + ", ".join(f"{k}={v}" for k, v in stats.items()))
    if failed:
        sys.exit(f"{len(failed)} files failed after retries (see {logs / (stem + '_failed.txt')}); "
                 "month not written, rerun to retry")
    if old is not None:
        have = set(zip(old["url"], old["company_id"]))
        df = pd.concat([old.drop(columns="timestamp_precision", errors="ignore"),
                        df[[(u, c) not in have for u, c in zip(df["url"], df["company_id"])]]],
                       ignore_index=True).sort_values(["company_id", "GKGRECORDID"]).reset_index(drop=True)
    p = write_month(df, args.out, args.period, args.month)
    if args.period == "contract":
        scanned_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(sorted(done | want), columns=["company_id", "day"]).to_parquet(scanned_path, index=False)
    print(f"{args.period} {args.month}: {len(df)} (URL, company) rows -> {p}")


if __name__ == "__main__":
    main()
