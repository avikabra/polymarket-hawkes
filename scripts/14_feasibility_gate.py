"""Script 14: Pre-analysis feasibility gate per plan §5.

Checks per-category thresholds:
  - >=200 resolved markets per category
  - Median >=10 verified articles per market
  - Median >=50 trades per market
  - >=50 rows in shock_embeddings.parquet's train split (real regression usability)
  - >=70% body_text_available among VERIFIED articles (the actual body-fetch target)

Exits with code 1 if any threshold fails, blocking make focal.
On success, writes data/analysis/_FOCAL_SUCCESS.

Recalibrated 2026-09-29 (see reports/bouchet_overnight_run_status.md) after the first
real end-to-end run exposed two metrics measuring the wrong thing:

  - The original "minute-precision %" check assumed an RSS-heavy corpus. This project's
    corpus is ~99.98% GDELT (day precision by design — see CLAUDE.md's own invariant),
    so that check could never pass regardless of data quality; it was measuring corpus
    composition, not real feasibility. Replaced with a direct check on whether
    scripts/13_purge_and_compute_shocks.py's ridge regression actually got enough
    TRAIN rows to fit (>=50, a standard floor for a 5-fold CV to be stable) — this
    measures real downstream usability instead of an inapplicable proxy. Only
    y_logit_24h has meaningful coverage in this corpus (valid_1h = valid_6h = 0% in
    the overnight run) — see reaction_windows.py's day-precision exclusion — so
    train_n here is inherently a 24h-window signal; that's expected, not a bug.
  - The original body-text-coverage % divided fetched bodies by the FULL raw corpus
    (~546k articles), but scripts/06_fetch_article_bodies.py is deliberately run
    --verified-only (see the Makefile) and only ever targets the verified article set
    (9,795 articles in the overnight run). Measuring against the full corpus made an
    87.1%-successful fetch look like 1.6% coverage. Fixed to use the verified set as
    the denominator, per category.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
CONTRACT_GROUPS_PATH = Path("data/polymarket/contract_groups.parquet")
TRADES_DIR = Path("data/polymarket/trades")
DB_PATH = Path("data/matches/matches.db")
BODIES_DIR = Path("data/news/bodies")
ANALYSIS_DIR = Path("data/analysis")
SHOCK_EMB_PATH = Path("data/analysis/shock_embeddings.parquet")

_THRESHOLDS = {
    "min_markets_per_category": 200,
    "median_verified_articles_per_market": 10,
    "median_trades_per_market": 50,
    "min_train_n_for_regression": 50,
    "min_body_text_available_pct": 70.0,
}


def _trade_counts_per_market() -> dict[str, int]:
    """Return {market_id: trade_count} from partitioned trades parquet."""
    if not TRADES_DIR.exists():
        return {}
    counts: dict[str, int] = {}
    for p in TRADES_DIR.rglob("part-*.parquet"):
        # Filename convention: part-{market_id}.parquet
        market_id = p.stem.replace("part-", "")
        df = pd.read_parquet(p, columns=["market_id"])
        counts[market_id] = counts.get(market_id, 0) + len(df)
    return counts


def _train_n_per_category() -> dict[str, int]:
    """Real train-split row counts per category, from script 13's actual regression
    output — direct evidence of downstream usability, not a proxy metric. A category
    absent from shock_embeddings.parquet entirely (e.g. every row failed the
    _CHAR_COLS dropna) counts as 0, same as a category with no train rows."""
    if not SHOCK_EMB_PATH.exists():
        return {}
    df = pd.read_parquet(SHOCK_EMB_PATH, columns=["category", "split"])
    train_counts = df[df["split"] == "train"].groupby("category").size()
    return {str(k): int(v) for k, v in train_counts.items()}


def _verified_articles_per_category(universe_df: pd.DataFrame) -> dict[str, set[str]]:
    """Verified article_ids per category, via matches.db + contract_groups fan-out.

    Mirrors _verified_per_market's group->market fan-out, but keyed by category
    (universe_df["category"]) instead of collapsed to a count, so body-text coverage
    can be measured against the correct denominator: articles actually verified for
    that category, not the full raw corpus (see module docstring).
    """
    if not DB_PATH.exists() or not CONTRACT_GROUPS_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT group_id, article_id FROM verifications WHERE is_match=1"
    ).fetchall()
    conn.close()
    group_articles: dict[str, set[str]] = {}
    for gid, aid in rows:
        group_articles.setdefault(str(gid), set()).add(str(aid))

    market_category = universe_df.set_index(universe_df["market_id"].astype(str))["category"]
    contract_groups_df = pd.read_parquet(CONTRACT_GROUPS_PATH)
    cat_articles: dict[str, set[str]] = {}
    for _, row in contract_groups_df.iterrows():
        articles = group_articles.get(str(row["group_id"]))
        if not articles:
            continue
        cats = {
            market_category.get(str(m))
            for m in row["member_market_ids"]
            if str(m) in market_category.index
        }
        for cat in cats:
            if cat is None:
                continue
            cat_articles.setdefault(str(cat), set()).update(articles)
    return cat_articles


def _verified_per_market() -> dict[str, int]:
    """Verified article counts, fanned out from groups to member markets.

    matches.db is group-keyed (schema v2, see scripts 08/09/10) — verifications
    has no market_id column. A verified (group, article) match applies to the
    whole group, so — matching the same group->market fan-out scripts 08/12 use —
    each member market of a matched group inherits that group's verified count.
    """
    if not DB_PATH.exists() or not CONTRACT_GROUPS_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT group_id, COUNT(*) FROM verifications WHERE is_match=1 GROUP BY group_id"
    ).fetchall()
    conn.close()
    group_counts = {str(g): int(c) for g, c in rows}

    contract_groups_df = pd.read_parquet(CONTRACT_GROUPS_PATH)
    market_counts: dict[str, int] = {}
    for _, row in contract_groups_df.iterrows():
        count = group_counts.get(str(row["group_id"]), 0)
        if count == 0:
            continue
        for market_id in row["member_market_ids"]:
            market_counts[str(market_id)] = market_counts.get(str(market_id), 0) + count
    return market_counts


def main() -> int:
    if not UNIVERSE_PATH.exists():
        print("FAIL: universe.parquet not found.")
        return 1

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    verified_per_market = _verified_per_market()
    trade_counts = _trade_counts_per_market()
    train_n_per_category = _train_n_per_category()
    verified_articles_per_category = _verified_articles_per_category(universe_df)

    fetched_ids: set[str] = set()
    if BODIES_DIR.exists():
        fetched_ids = {p.stem for p in BODIES_DIR.glob("*.txt") if p.stat().st_size > 0}

    pass_all = True
    print(f"\n{'Category':<18} {'Markets':>8} {'Med.Art':>8} {'Med.Trd':>8} {'TrainN':>7} {'Body%':>6} {'STATUS':>8}")
    print("-" * 74)

    categories = universe_df["category"].unique() if "category" in universe_df.columns else []

    for cat in sorted(categories):
        cat_markets = universe_df[universe_df["category"] == cat]
        n_markets = len(cat_markets)
        market_ids = set(cat_markets["market_id"].astype(str).tolist())

        # Verified articles per market
        art_counts = [verified_per_market.get(m, 0) for m in market_ids]
        med_art = float(pd.Series(art_counts).median()) if art_counts else 0.0

        # Trade counts per market
        trd_counts = [trade_counts.get(m, 0) for m in market_ids]
        med_trd = float(pd.Series(trd_counts).median()) if trd_counts else 0.0

        # Real regression usability (train rows in shock_embeddings.parquet), not a
        # timestamp-precision proxy — see module docstring for why.
        train_n = train_n_per_category.get(str(cat), 0)

        # Body-text coverage against the VERIFIED article set for this category (the
        # actual body-fetch --verified-only target), not the full raw corpus.
        cat_verified = verified_articles_per_category.get(str(cat), set())
        if cat_verified:
            body_pct = 100.0 * len(fetched_ids & cat_verified) / len(cat_verified)
        else:
            body_pct = 0.0

        ok = (
            n_markets >= _THRESHOLDS["min_markets_per_category"]
            and med_art >= _THRESHOLDS["median_verified_articles_per_market"]
            and med_trd >= _THRESHOLDS["median_trades_per_market"]
            and train_n >= _THRESHOLDS["min_train_n_for_regression"]
            and body_pct >= _THRESHOLDS["min_body_text_available_pct"]
        )
        if not ok:
            pass_all = False

        status = "PASS" if ok else "FAIL"
        print(
            f"{cat:<18} {n_markets:>8} {med_art:>8.1f} {med_trd:>8.0f} "
            f"{train_n:>7} {body_pct:>5.1f}%   {status}"
        )

    print("-" * 74)
    print(f"\nThresholds: markets>={_THRESHOLDS['min_markets_per_category']}  "
          f"med_art>={_THRESHOLDS['median_verified_articles_per_market']}  "
          f"med_trd>={_THRESHOLDS['median_trades_per_market']}  "
          f"train_n>={_THRESHOLDS['min_train_n_for_regression']}  "
          f"body>={_THRESHOLDS['min_body_text_available_pct']}%")

    if pass_all:
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        (ANALYSIS_DIR / "_FOCAL_SUCCESS").touch()
        print("\nFEASIBILITY GATE PASSED — _FOCAL_SUCCESS written.")
        return 0
    else:
        print("\nFEASIBILITY GATE FAILED — see failed rows above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
