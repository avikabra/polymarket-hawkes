"""Script 09c: Tune Thread 1's joint-score weights (w1, w2) with a held-out split.

novel_math_design.md's Thread 1 formula is
  match_quality_logit = w1 * logit(embedding_score) + w2 * liquidity_z
fixed at w1=w2=1.0 — "tuning against labels is a stretch goal, not required."
scripts/09b_matching_ablation.py already shows this default beats embedding-only
by a wide margin (rho~0.51 vs ~0.23 on real data). This script asks a narrower
question: can any (w1, w2) beat the default OUT OF SAMPLE, or does the default
already capture what these two signals can offer together?

Methodology (the point of this script, not an afterthought):
  1. Split verified pairs into a TUNING set and a held-out EVAL set, split by
     group_id (not per-pair) so no company's pairs leak across the split — a
     deterministic hash of group_id assigns ~70% to tuning, ~30% to eval. Group
     split, not temporal: nothing here is about detecting drift over time (that's
     scripts 13/14's job with real dates); it's about not letting the tuner see
     the same company's pairs it's then "evaluated" on, which a random per-pair
     split would allow (many pairs per group share correlated liquidity noise).
  2. Grid search (w1, w2) on the TUNING set only, maximizing Spearman rho against
     realized |y_logit_24h| (src.analysis.matching_ablation.grid_search_weights).
  3. Report BOTH the tuned weights' rho AND the default (1.0, 1.0) rho, on the
     held-out EVAL set only — apples to apples, so tuning gains (if any) are
     real, not an artifact of evaluating on the data used to pick the weights.

Does NOT update src/matching/joint_verifier.py's defaults — that's a real
methodological change to Thread 1's already-reported result, for a human to
decide, not something this script does unilaterally.

Reuses the exact same per-pair I/O as scripts/09b_matching_ablation.py (group
member bars, liquidity signal, reaction windows) via src/matching/joint_scoring.py
and src/matching/liquidity_signal.py — only difference is this script keeps
liquidity_z (which 09b computes and discards) since the grid search needs it to
recompute match_quality_logit at arbitrary (w1, w2) without re-running the
expensive bars/liquidity computation per grid point.

Needs real matches.db + bars_1min (Bouchet only) to produce real numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.analysis.matching_ablation import (
    compute_single_score_correlation,
    grid_search_weights,
    match_quality_score,
)
from src.analysis.reaction_windows import compute_reaction_windows
from src.matching.joint_scoring import (
    group_member_map,
    group_resolved_at,
    load_group_member_bars,
    market_resolved_at_map,
    parse_article_ts,
    score_pair_joint,
)
from src.utils import get_logger

DB_PATH = Path("data/matches/matches.db")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
CONTRACT_GROUPS_PATH = Path("data/polymarket/contract_groups.parquet")
ANALYSIS_DIR = Path("data/analysis")
OUT_PATH = ANALYSIS_DIR / "matching_weight_tuning.parquet"

DEFAULT_WEIGHT_GRID = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]
TUNING_FRACTION_PCT = 70  # ~70% of group_ids -> tuning, ~30% -> held-out eval

log = get_logger(__name__)


def _split_bucket(group_id: str) -> str:
    """Deterministic group_id -> 'tuning' | 'eval', ~70/30 (see module docstring
    for why the split is by group_id, not per-pair or temporal)."""
    digest = hashlib.md5(group_id.encode()).hexdigest()
    return "tuning" if int(digest, 16) % 100 < TUNING_FRACTION_PCT else "eval"


def _realized_abs_y_logit_24h(
    member_bars: dict[str, pd.DataFrame],
    article_ts: pd.Timestamp | None,
    timestamp_precision: str,
    market_resolved_at_: pd.Timestamp | None,
) -> float | None:
    """Same reduction as scripts/09b_matching_ablation.py's private helper of the
    same name: max |y_logit_24h| across a group's member markets, pinned to the
    24h window (the only real target in this corpus — see 09b's docstring)."""
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


def _build_score_table(
    conn: sqlite3.Connection,
    group_members: dict[str, list[str]],
    resolved_at_map: dict[str, pd.Timestamp | None],
    sample: int | None,
    seed: int,
) -> pd.DataFrame:
    """Like scripts/09b_matching_ablation.py's private helper of the same name,
    but keeps liquidity_z (09b discards it after computing the default-weight
    joint_score) since the grid search needs it to try other weights."""
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

        # score_pair_joint always uses the default (1.0, 1.0) internally; we only
        # want its liquidity_z/price_impact outputs here, not its match_strength
        # (the grid search recomputes match_strength itself per (w1, w2)).
        _default_result, liquidity = score_pair_joint(
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
            "liquidity_z": liquidity["volume_z"],
            "realized_abs_y_logit_24h": realized,
            "split": _split_bucket(group_id),
        })

    if skipped_no_members:
        log.warning("pairs skipped (group has no member markets)", count=skipped_no_members)

    return pd.DataFrame(out_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Limit to N randomly-sampled verified pairs before the tuning/eval split.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--weight-grid", type=float, nargs="+", default=DEFAULT_WEIGHT_GRID,
        help=f"Candidate values for both w1 and w2 (default: {DEFAULT_WEIGHT_GRID}).",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"{DB_PATH} not found — run scripts 08-09 first. Expected on Bouchet.")
        return
    if not UNIVERSE_PATH.exists() or not CONTRACT_GROUPS_PATH.exists():
        print("universe.parquet / contract_groups.parquet not found — run scripts 01/08 first.")
        return

    conn = sqlite3.connect(DB_PATH)
    n_verified = conn.execute("SELECT COUNT(*) FROM verifications").fetchone()[0]
    if n_verified == 0:
        print("No verified pairs in matches.db yet — run script 09 first.")
        conn.close()
        return

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    contract_groups_df = pd.read_parquet(CONTRACT_GROUPS_PATH)
    group_members = group_member_map(contract_groups_df)
    resolved_at_map = market_resolved_at_map(universe_df)

    score_df = _build_score_table(conn, group_members, resolved_at_map, args.sample, args.seed)
    conn.close()

    if score_df.empty:
        print("No scoreable pairs. Nothing to tune.")
        return

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(score_df), OUT_PATH)

    tuning_df = score_df[score_df["split"] == "tuning"].dropna(subset=["realized_abs_y_logit_24h"])
    eval_df = score_df[score_df["split"] == "eval"].dropna(subset=["realized_abs_y_logit_24h"])

    n_groups = score_df["group_id"].nunique()
    n_tuning_groups = score_df.loc[score_df["split"] == "tuning", "group_id"].nunique()
    n_eval_groups = score_df.loc[score_df["split"] == "eval", "group_id"].nunique()

    print(f"Pairs scored:                 {len(score_df)}")
    print(f"Distinct groups:               {n_groups}  (tuning={n_tuning_groups}  eval={n_eval_groups})")
    print(f"Tuning pairs w/ real 24h window: {len(tuning_df)}")
    print(f"Eval pairs w/ real 24h window:   {len(eval_df)}")
    print(f"Written:                       {OUT_PATH}")
    print()

    if len(tuning_df) < 3 or len(eval_df) < 3:
        print("DEGENERATE: too few pairs with a real 24h window in tuning and/or eval split "
              "to report a result. Not a positive or negative finding — not enough real data "
              "yet (expected on a local dev machine; run on Bouchet for a real result).")
        return

    grid_results = grid_search_weights(
        tuning_df["embedding_score"], tuning_df["liquidity_z"],
        tuning_df["realized_abs_y_logit_24h"], args.weight_grid,
    )
    print("=== Grid search on TUNING set (top 5 by rho) ===")
    print(grid_results.head(5).to_string(index=False))
    print()

    best = grid_results.iloc[0]
    if bool(best["degenerate"]):
        print("DEGENERATE: even the best grid point is degenerate on the tuning set. "
              "Not enough real data yet.")
        return
    best_w1, best_w2 = float(best["w1"]), float(best["w2"])

    tuned_score_eval = match_quality_score(eval_df["embedding_score"], eval_df["liquidity_z"], best_w1, best_w2)
    default_score_eval = match_quality_score(eval_df["embedding_score"], eval_df["liquidity_z"], 1.0, 1.0)

    tuned_eval_stats = compute_single_score_correlation(tuned_score_eval, eval_df["realized_abs_y_logit_24h"])
    default_eval_stats = compute_single_score_correlation(default_score_eval, eval_df["realized_abs_y_logit_24h"])

    print(f"Best tuning-set weights: w1={best_w1}, w2={best_w2}  "
          f"(tuning rho={best['rho']:.4f}, n={int(best['n_used'])})")
    print()
    print("=== Held-out EVAL set (never touched by the grid search) ===")
    if tuned_eval_stats["degenerate"] or default_eval_stats["degenerate"]:
        print("DEGENERATE on eval set — cannot compare out of sample with this little data.")
        return
    print(f"  Tuned  (w1={best_w1}, w2={best_w2}): rho={tuned_eval_stats['rho']:.4f}  "
          f"p={tuned_eval_stats['p']:.4g}  n={tuned_eval_stats['n_used']}")
    print(f"  Default(w1=1.0, w2=1.0):        rho={default_eval_stats['rho']:.4f}  "
          f"p={default_eval_stats['p']:.4g}  n={default_eval_stats['n_used']}")
    print()

    delta = tuned_eval_stats["rho"] - default_eval_stats["rho"]
    if abs(delta) < 0.02:
        print(f"Result: tuned and default weights perform about the same out of sample "
              f"(Δrho={delta:+.4f}). Tuning does not appear to help — the default w1=w2=1.0 "
              f"already captures what these two signals offer together. Do NOT update the "
              f"defaults on this evidence.")
    elif delta > 0:
        print(f"Result: tuned weights beat the default out of sample (Δrho={delta:+.4f}). "
              f"This is real held-out evidence, not tuning-set overfitting — worth considering "
              f"updating src/matching/joint_verifier.py's defaults, but that's a methodology "
              f"decision for a human, not done here.")
    else:
        print(f"Result: tuned weights UNDERPERFORM the default out of sample (Δrho={delta:+.4f}) "
              f"— the tuning-set grid search overfit to tuning-set noise. Do NOT update the "
              f"defaults; w1=w2=1.0 remains the better choice on this evidence.")


if __name__ == "__main__":
    main()
