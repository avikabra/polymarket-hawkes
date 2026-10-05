"""Script 09b: Thread 1 matching ablation (novel_math_design.md "Validation (Q3) —
REQUIRED, not optional").

For every verified (group, article) pair in matches.db, computes:
  (a) embedding-only score  — candidates.embedding_score (already stored by script 08)
  (b) joint score            — verify_pair_joint's match_strength, recomputed here via
                                src/matching/joint_scoring.py (the same helper script 09's
                                --joint path uses, so this is not a second implementation)
  (c) realized |y_logit_24h| — via reaction_windows.compute_reaction_windows on each
                                member market's bars, max |y_logit_24h| across members
                                (mirrors liquidity_signal.py's own price_impact pattern).
                                y_logit_24h is the ONLY real target in this corpus (Fix 1:
                                valid_1h = valid_6h = 0% corpus-wide) — 1h/6h are not
                                computed here.

Reports the Spearman correlation of (a) and (b) against (c) — the comparison table is
the acceptance artifact for all of Thread 1. Prints to stdout and writes
data/analysis/matching_ablation.parquet (per-pair scores) for inspection.

Uses ALL verified pairs (is_match 0 or 1), not just is_match=1 — restricting to matches
only would select on a quantity partly derived from embedding_score itself (rule_verifier
and the joint verifier both gate on it), which would bias the correlation. Not specified
in the plan doc — flagging this choice per task instructions.

Needs real matches.db (script 08-09 output) + real data/polymarket/bars_1min to produce
real numbers. Both are expected to exist only on Bouchet, not on a local dev machine —
this script degrades to a clear "nothing to do" message rather than crashing when they're
absent; see tests/test_09b_matching_ablation.py for a synthetic-fixture test of the
correlation math in isolation.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.analysis.matching_ablation import (
    compute_score_reaction_correlations,
    compute_single_score_correlation,
)
from src.analysis.reaction_windows import compute_reaction_windows
from src.matching.joint_scoring import (
    group_company_aliases_map,
    group_member_map,
    group_resolved_at,
    load_group_member_bars,
    market_resolved_at_map,
    parse_article_ts,
    score_pair_joint,
)
from src.news.normalizer import build_matching_text_corpus
from src.utils import get_logger

GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")

DB_PATH = Path("data/matches/matches.db")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
CONTRACT_GROUPS_PATH = Path("data/polymarket/contract_groups.parquet")
ANALYSIS_DIR = Path("data/analysis")
OUT_PATH = ANALYSIS_DIR / "matching_ablation.parquet"

log = get_logger(__name__)


def _realized_abs_y_logit_24h(
    member_bars: dict[str, pd.DataFrame],
    article_ts: pd.Timestamp | None,
    timestamp_precision: str,
    market_resolved_at_: pd.Timestamp | None,
) -> float | None:
    """Max |y_logit_24h| across a group's member markets, or None if no member has
    an achievable (valid) 24h window. Same reduction liquidity_signal.py's own
    price_impact uses, but pinned to window_hours=24 regardless of timestamp
    precision (compute_liquidity_response uses a precision-dependent window,
    which would give a <24h reaction for minute-precision articles — wrong
    target for this ablation per the plan doc's Fix 1)."""
    if article_ts is None:
        return None
    impacts = []
    for bars_df in member_bars.values():
        if bars_df.empty:
            continue
        windows = compute_reaction_windows(
            article_ts=article_ts,
            timestamp_precision=timestamp_precision,
            market_resolved_at=market_resolved_at_,
            bars_df=bars_df,
            window_hours=[24],
        )
        if windows.get("valid_24h") and windows.get("y_logit_24h") is not None:
            impacts.append(abs(windows["y_logit_24h"]))
    return max(impacts) if impacts else None


def _load_article_entities() -> dict[str, list[str]]:
    """article_id -> entities, from the same normalized corpus scripts 07/08/09 use.
    Added 2026-10-05 for the entity-grounding term — see joint_verifier.py."""
    df = build_matching_text_corpus(str(GDELT_DIR), str(FEEDS_DIR))
    if df.empty:
        return {}
    # `entities` is numpy-array-valued — `arr or []` raises ValueError ("truth value
    # of an array... is ambiguous") for any array with >1 element, so this must be an
    # explicit None check, not Python's `or`.
    return {
        row["article_id"]: list(row["entities"]) if row["entities"] is not None else []
        for _, row in df.iterrows()
    }


def _build_score_table(
    conn: sqlite3.Connection,
    group_members: dict[str, list[str]],
    resolved_at_map: dict[str, pd.Timestamp | None],
    article_entities: dict[str, list[str]],
    group_aliases: dict[str, list[str]],
    sample: int | None,
    seed: int,
) -> pd.DataFrame:
    rows = conn.execute(
        "SELECT v.group_id, v.article_id, c.embedding_score, "
        "       c.article_published_at, c.timestamp_precision "
        "FROM verifications v "
        "JOIN candidates c ON v.group_id = c.group_id AND v.article_id = c.article_id"
    ).fetchall()

    if sample is not None and len(rows) > sample:
        df_rows = pd.DataFrame(rows).sample(n=sample, random_state=seed)
        rows = list(df_rows.itertuples(index=False, name=None))

    out_rows = []
    skipped_no_members = 0
    for group_id, article_id, embedding_score, pub_at, prec in rows:
        group_id = str(group_id)
        member_ids = group_members.get(group_id, [])
        if not member_ids:
            skipped_no_members += 1
            continue

        member_bars = load_group_member_bars(member_ids)
        article_ts = parse_article_ts(pub_at)
        resolved_at = group_resolved_at(member_ids, resolved_at_map)
        entities = article_entities.get(article_id, [])
        company_aliases = group_aliases.get(group_id, [])

        result, _liquidity = score_pair_joint(
            embedding_score=embedding_score,
            article_ts=article_ts,
            timestamp_precision=str(prec),
            member_bars=member_bars,
            market_resolved_at=resolved_at,
            entities=entities,
            company_aliases=company_aliases,
        )
        # Same member_bars/liquidity inputs, entities withheld — isolates the
        # entity-grounding term's marginal effect on today's data, with no
        # confound from other matches.db changes between runs (2026-10-05: the
        # naive before/after-in-time comparison turned out to be confounded by
        # unrelated matches.db changes made between the original 0.5124 run and
        # today — same n_total but different n_used/embedding_rho each time).
        result_no_entity, _ = score_pair_joint(
            embedding_score=embedding_score,
            article_ts=article_ts,
            timestamp_precision=str(prec),
            member_bars=member_bars,
            market_resolved_at=resolved_at,
        )
        realized = _realized_abs_y_logit_24h(member_bars, article_ts, str(prec), resolved_at)

        out_rows.append({
            "group_id": group_id,
            "article_id": article_id,
            "embedding_score": float(embedding_score),
            "joint_score": result.match_strength,
            "joint_score_no_entity": result_no_entity.match_strength,
            "realized_abs_y_logit_24h": realized,
        })

    if skipped_no_members:
        log.warning("pairs skipped (group has no member markets)", count=skipped_no_members)

    return pd.DataFrame(out_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Limit to N randomly-sampled verified pairs (default: all — the plan doc's "
             "stated preference when runtime allows).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed (with --sample).")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"{DB_PATH} not found — run scripts 08-09 first. "
              "Expected on Bouchet, not necessarily on a local dev machine.")
        return
    if not UNIVERSE_PATH.exists() or not CONTRACT_GROUPS_PATH.exists():
        print("universe.parquet / contract_groups.parquet not found — run scripts 01/08 first.")
        return

    conn = sqlite3.connect(DB_PATH)
    n_verified = conn.execute("SELECT COUNT(*) FROM verifications").fetchone()[0]
    if n_verified == 0:
        print("No verified pairs in matches.db yet — run script 09 first. Nothing to ablate.")
        conn.close()
        return

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    contract_groups_df = pd.read_parquet(CONTRACT_GROUPS_PATH)
    group_members = group_member_map(contract_groups_df)
    resolved_at_map = market_resolved_at_map(universe_df)
    group_aliases = group_company_aliases_map(contract_groups_df)
    article_entities = _load_article_entities()

    score_df = _build_score_table(
        conn, group_members, resolved_at_map, article_entities, group_aliases, args.sample, args.seed,
    )
    conn.close()

    if score_df.empty:
        print("No scoreable pairs (every verified pair's group had no member markets). "
              "Nothing to ablate.")
        return

    stats = compute_score_reaction_correlations(score_df)

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(score_df), OUT_PATH)

    print(f"Pairs scored:                 {len(score_df)}")
    print(f"Pairs with a real 24h window: {stats['n_used']}")
    print(f"Written:                      {OUT_PATH}")
    print()
    if stats["degenerate"]:
        print("DEGENERATE: too few pairs with a real 24h window (or all tied) to report a "
              "correlation. This is not a positive or negative finding — it means this run "
              "doesn't have enough real data yet (expected on a local dev machine; run on "
              "Bouchet with real matches.db + bars_1min for a real result).")
    else:
        usable = score_df.dropna(subset=["realized_abs_y_logit_24h"])
        no_entity_stats = compute_single_score_correlation(
            usable["joint_score_no_entity"], usable["realized_abs_y_logit_24h"],
        )
        print(f"Spearman(embedding-only score,      |y_logit_24h|): "
              f"rho={stats['embedding_rho']:.4f}  p={stats['embedding_p']:.4g}")
        print(f"Spearman(joint score, no entity term, |y_logit_24h|): "
              f"rho={no_entity_stats['rho']:.4f}  p={no_entity_stats['p']:.4g}")
        print(f"Spearman(joint score, with entity term, |y_logit_24h|): "
              f"rho={stats['joint_rho']:.4f}  p={stats['joint_p']:.4g}")
        print()
        print("(no-entity-term row is the same data/code as the original acceptance test, "
              "recomputed now, in the same process as the entity-term row — isolates the "
              "entity term's marginal effect with no time-based confound)")
        print()
        if abs(stats["joint_rho"]) > abs(stats["embedding_rho"]):
            print("Result: joint score correlates MORE strongly with realized |y_logit_24h| "
                  "than embedding-only score.")
        elif abs(stats["joint_rho"]) < abs(stats["embedding_rho"]):
            print("Result: joint score correlates LESS strongly with realized |y_logit_24h| "
                  "than embedding-only score (negative result for Thread 1's liquidity signal "
                  "— report honestly, do not tune to force a different outcome).")
        else:
            print("Result: joint and embedding-only scores correlate equally with realized "
                  "|y_logit_24h|.")


if __name__ == "__main__":
    main()
