"""Script 01: Discover the focal market universe from Gamma API (Weeks 7-9 rewrite).

Discovery strategy: day-sliced enumeration via GammaClient.enumerate_markets
(avoids the ~2,100-offset ceiling on the /markets endpoint).  Classification
is delegated to classify_company_contract / extract_strike_fields.  No volume
floor is applied at discovery; all accepted markets are written verbatim.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.polymarket.company_filter import classify_company_contract, extract_strike_fields
from src.polymarket.gamma import GammaClient
from src.schemas import Market
from src.utils import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _to_parquet(markets: list[Market], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not markets:
        pq.write_table(pa.table({}), out_path)
        return
    records = []
    for m in markets:
        d = m.model_dump()
        d["tags"] = json.dumps(d["tags"])
        records.append(d)
    df = pd.DataFrame(records)
    for col in ["created_at", "end_at", "resolved_at"]:
        df[col] = pd.to_datetime(df[col], utc=True)
    pq.write_table(pa.Table.from_pandas(df), out_path)


def _parse_iso_date(s: str) -> datetime:
    """Parse an ISO date string (YYYY-MM-DD) to a UTC midnight datetime."""
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    focal = _load_yaml("config/focal.yaml")["focal"]

    parser = argparse.ArgumentParser(description="Discover Polymarket company-contract universe.")
    parser.add_argument(
        "--start",
        default=focal["discovery_start_date"],
        help="ISO start date (inclusive), overrides focal.discovery_start_date",
    )
    parser.add_argument(
        "--end",
        default=focal["discovery_end_date"],
        help="ISO end date (exclusive upper bound), overrides focal.discovery_end_date",
    )
    args = parser.parse_args()

    start_dt = _parse_iso_date(args.start)
    end_dt = _parse_iso_date(args.end)

    log.info(
        "starting discovery",
        extra={"start": args.start, "end": args.end},
    )

    client = GammaClient()
    seen: set[str] = set()
    markets: list[Market] = []

    async for raw in client.enumerate_markets(
        start_dt,
        end_dt,
        inter_page_sleep=focal["enumeration_sleep_inter_page"],
        inter_day_sleep=focal["enumeration_sleep_inter_day"],
    ):
        cid = raw.get("conditionId", "")
        if not cid or cid in seen:
            continue
        seen.add(cid)

        cls = classify_company_contract(raw)
        if cls is None:
            continue

        family = cls["contract_family"]
        sf = (
            extract_strike_fields(raw.get("question", ""), end_at=raw.get("endDate"))
            if family.endswith("_ladder")
            else None
        )

        try:
            m = client.parse_market(raw, classification=cls, strike_fields=sf)
        except Exception as exc:
            log.warning("parse failed", extra={"condition_id": cid, "error": str(exc)})
            continue

        markets.append(m)

    # ── Group assignment ─────────────────────────────────────────────────────
    _LADDER_FAMILIES = {
        "price_ladder", "market_cap_ladder", "valuation_ladder",
        "revenue_ladder", "other_ladder",
    }
    updated: list[Market] = []
    for m in markets:
        if m.contract_family in _LADDER_FAMILIES:
            expiry = m.price_expiry_month or m.end_at.strftime("%Y-%m")
            metric = (
                m.contract_family.replace("_ladder", "")
                if m.contract_family != "other_ladder"
                else "other"
            )
            group_id = f"{m.company_id}_{metric}_{expiry}"
            group_role = "child"
        else:
            # corporate_event and any unrecognised family → standalone
            group_id = m.market_id
            group_role = "standalone"
        updated.append(m.model_copy(update={"group_id": group_id, "group_role": group_role}))
    markets = updated

    # ── Loud-fail guards ─────────────────────────────────────────────────────
    if not markets:
        raise RuntimeError(
            "no company contracts discovered — check date window, company dict, "
            "or Gamma API availability"
        )

    n_primary = sum(1 for m in markets if m.is_primary_sample)
    if n_primary == 0:
        raise RuntimeError(
            "is_primary_sample count is 0 — contract_family classification is broken"
        )

    n_ladders = sum(1 for m in markets if m.contract_family.endswith("_ladder"))
    n_events = sum(1 for m in markets if m.contract_family == "corporate_event")
    if n_ladders == 0 and n_events == 0:
        raise RuntimeError(
            "no ladder or corporate_event contracts found — classifier produced no accepted markets"
        )

    # ── Write universe.parquet ───────────────────────────────────────────────
    universe_path = Path("data/polymarket/universe.parquet")
    _to_parquet(markets, universe_path)
    log.info("wrote universe", extra={"path": str(universe_path), "n": len(markets)})

    # ── Build contract_groups.parquet sidecar ────────────────────────────────
    groups: dict[str, dict] = {}
    for m in markets:
        gid = m.group_id
        if gid not in groups:
            # Derive ladder_metric from contract_family
            if m.contract_family.endswith("_ladder"):
                ladder_metric: str | None = m.contract_family.replace("_ladder", "") if m.contract_family != "other_ladder" else "other"
            else:
                ladder_metric = None
            groups[gid] = {
                "group_id": gid,
                "company_name": m.company_name,
                "company_id": m.company_id,
                "ticker": m.ticker,
                "contract_family": m.contract_family,
                "ladder_metric": ladder_metric,
                "price_expiry_month": m.price_expiry_month,
                "member_market_ids": [],
                "strikes": [],
            }
        groups[gid]["member_market_ids"].append(m.market_id)
        # Collect strike_price for any ladder family
        if m.contract_family.endswith("_ladder") and m.strike_price is not None:
            groups[gid]["strikes"].append(m.strike_price)

    group_rows = []
    for g in groups.values():
        g["strikes"] = sorted(set(g["strikes"]))
        g["n_members"] = len(g["member_market_ids"])
        group_rows.append(g)

    cg_df = pd.DataFrame(group_rows)
    cg_path = Path("data/polymarket/contract_groups.parquet")
    cg_path.parent.mkdir(parents=True, exist_ok=True)
    cg_df.to_parquet(cg_path, index=False)
    log.info("wrote contract_groups", extra={"path": str(cg_path), "n_groups": len(group_rows)})

    # ── Summary printout ─────────────────────────────────────────────────────
    family_counts: dict[str, int] = defaultdict(int)
    family_groups: dict[str, set] = defaultdict(set)
    company_counts: dict[str, int] = defaultdict(int)
    for m in markets:
        family_counts[m.contract_family] += 1
        family_groups[m.contract_family].add(m.group_id)
        if m.company_name:
            company_counts[m.company_name] += 1

    _ALL_FAMILIES = (
        "price_ladder", "market_cap_ladder", "valuation_ladder",
        "revenue_ladder", "other_ladder", "corporate_event", "other",
    )
    print(f"\n{'contract_family':<22} {'total':>6}  {'groups':>6}")
    print("-" * 38)
    for fam in _ALL_FAMILIES:
        cnt = family_counts.get(fam, 0)
        if cnt == 0:
            continue
        grps = len(family_groups.get(fam, set()))
        print(f"{fam:<22} {cnt:>6}  {grps:>6}")

    top_companies = sorted(company_counts.items(), key=lambda x: -x[1])[:10]
    print("\nTop companies by contract count:")
    for name, cnt in top_companies:
        print(f"  {name}: {cnt}")

    print(f"\nTotal markets : {len(markets)}")
    print(f"Total groups  : {len(group_rows)}")

    # Example group_ids
    example_gids = [g["group_id"] for g in group_rows[:5]]
    print(f"Example group_ids: {example_gids}")

    Path("data/polymarket/_UNIVERSE_SUCCESS").touch()
    log.info("done", extra={"n_markets": len(markets), "n_groups": len(group_rows)})


if __name__ == "__main__":
    asyncio.run(main())
