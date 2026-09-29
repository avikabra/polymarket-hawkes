"""Script 12: Assemble the per-article VerifiedArticle dataset.

Joins:
  - matches.db verifications (group-keyed — schema v2, see scripts 08/09/10)
  - data/polymarket/contract_groups.parquet (group_id -> member_market_ids fan-out)
  - data/polymarket/bars_1min (LOCF reaction windows + market chars, per member market)
  - data/polymarket/universe.parquet (market metadata: contract_family, resolved_at)

Matching happens at the GROUP level, but a VerifiedArticle row is per-MARKET: each
verified (group, article) pair fans out into one row per member market of that group,
each priced against that market's own bars_1min series. prior_article_count is a
group-level statistic (verification is group-level) and is shared across a group's
fanned-out rows for the same article.

Writes: data/analysis/tuples.parquet (one row per VerifiedArticle)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.analysis.ladder_reaction import compute_ladder_adjusted_reactions
from src.analysis.market_chars import compute_market_chars
from src.analysis.reaction_windows import compute_reaction_windows
from src.news.normalizer import build_matching_text_corpus
from src.utils import assert_covers, get_logger, load_bars

DB_PATH = Path("data/matches/matches.db")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
CONTRACT_GROUPS_PATH = Path("data/polymarket/contract_groups.parquet")
ANALYSIS_DIR = Path("data/analysis")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")

log = get_logger(__name__)


def _load_config() -> dict:
    cfg_path = Path("config/analysis.yaml")
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f)
    return {}


def _load_article_meta() -> dict[str, dict]:
    """Article metadata via the shared normalizer (see src/news/normalizer.py A3 note) —
    consistent with scripts 07-09 rather than a separate raw parquet concat."""
    df = build_matching_text_corpus(str(GDELT_DIR), str(FEEDS_DIR))
    if df.empty:
        return {}
    return {
        row["article_id"]: row.to_dict()
        for _, row in df.iterrows()
    }


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    cfg = _load_config()
    window_hours: list[int] = cfg.get("reaction_windows_hours", [1, 6, 24])

    if not DB_PATH.exists():
        print("No matches.db — run scripts 08–10 first.")
        return

    conn = sqlite3.connect(DB_PATH)
    # ne.member_article_ids is a JSON array (TEXT column) — json_each() must be
    # invoked as a table-valued function to unnest it; it cannot be referenced as
    # a bare column prefix (an earlier version of this query did exactly that and
    # would raise "no such column: json_each.value" the moment this ran for real).
    rows = conn.execute(
        """
        SELECT v.group_id, v.article_id, v.is_match, v.match_strength,
               v.directional_impact, v.magnitude, v.news_type,
               c.article_published_at, c.timestamp_precision,
               ne.event_id
        FROM verifications v
        JOIN candidates c ON v.group_id=c.group_id AND v.article_id=c.article_id
        LEFT JOIN news_events ne ON ne.group_id = v.group_id
            AND EXISTS (
                SELECT 1 FROM json_each(ne.member_article_ids) je
                WHERE je.value = v.article_id
            )
        WHERE v.is_match=1
        """
    ).fetchall()
    conn.close()
    log.info("verified pairs (group-level)", count=len(rows))

    universe_df = pd.read_parquet(UNIVERSE_PATH)
    contract_groups_df = pd.read_parquet(CONTRACT_GROUPS_PATH)
    assert_covers(
        [GDELT_DIR, FEEDS_DIR],
        (cid for cid in universe_df["company_id"] if cid),
        (
            pd.Timestamp(universe_df["created_at"].min()).isoformat(),
            pd.Timestamp(universe_df["end_at"].max()).isoformat(),
        ),
    )
    market_info: dict[str, dict] = {
        str(row["market_id"]): row.to_dict()
        for _, row in universe_df.iterrows()
    }
    group_members: dict[str, list[str]] = {
        str(row["group_id"]): [str(m) for m in row["member_market_ids"]]
        for _, row in contract_groups_df.iterrows()
    }
    article_meta = _load_article_meta()

    # Prior article count is a GROUP-level statistic — verification happens once
    # per (group, article), not per member market — so it's keyed by group_id and
    # shared across all of a group's fanned-out market rows for the same article.
    verified_ts: dict[str, dict[str, pd.Timestamp]] = {}  # group_id -> {article_id: ts}
    for group_id, article_id, _, _, _, _, _, pub_at, prec, _ in rows:
        if pub_at:
            verified_ts.setdefault(str(group_id), {})[str(article_id)] = pd.Timestamp(pub_at)

    output_rows = []
    for group_id, article_id, is_match, match_strength, di, mag, news_type, pub_at, prec, event_id in rows:
        group_id = str(group_id)
        article_id = str(article_id)

        article_ts = pd.Timestamp(pub_at) if pub_at else None
        if article_ts is not None and article_ts.tzinfo is None:
            article_ts = article_ts.tz_localize("UTC")

        grp_ts_map = verified_ts.get(group_id, {})
        prior_count = sum(
            1 for aid, ts in grp_ts_map.items()
            if aid != article_id and article_ts is not None and ts < article_ts
        )

        # embedding_source will be filled by script 11; default headline_only here
        ameta = article_meta.get(article_id, {})
        embedding_source = "headline_only" if not ameta.get("body_text") else "full_text"

        member_market_ids = group_members.get(group_id, [])
        if not member_market_ids:
            log.warning("group has no member markets in universe", extra={"group_id": group_id})
            continue

        # Fan out: the matched news event applies to the whole group, but market
        # characteristics and reaction windows are inherently per-market — one
        # VerifiedArticle row per member market, each priced against its own bars.
        for market_id in member_market_ids:
            minfo = market_info.get(market_id, {})
            if not minfo:
                continue

            category = str(minfo.get("contract_family", ""))
            resolved_at_raw = minfo.get("resolved_at")
            # resolved_at_raw is NaN (not None) when missing — `if resolved_at_raw`
            # alone doesn't catch that (NaN is truthy in Python), which reached
            # compute_market_chars as pd.NaT and crashed on .timestamp().
            resolved_at = (
                pd.Timestamp(resolved_at_raw)
                if resolved_at_raw and pd.notna(resolved_at_raw)
                else None
            )
            if resolved_at is None:
                # DATA GAP, not a design choice — flag in any writeup that touches
                # time_to_resolution_days or the train/val/test split. universe.parquet's
                # resolved_at is NaT for all 6928 markets even though resolved_outcome
                # is 100% populated (every market genuinely resolved) and end_at is in
                # the past for all of them — script 01 (universe pull) never captured
                # the actual settlement timestamp. Falling back to the scheduled end_at
                # as the best available proxy for when resolution happened, rather than
                # leaving every row's time_to_resolution_days null (which previously
                # emptied every _CHAR_COLS dropna in purging.py, producing zero rows).
                end_at_raw = minfo.get("end_at")
                if end_at_raw and pd.notna(end_at_raw):
                    resolved_at = pd.Timestamp(end_at_raw)
            if resolved_at is not None and resolved_at.tzinfo is None:
                resolved_at = resolved_at.tz_localize("UTC")

            bars_df = load_bars(market_id)

            chars = compute_market_chars(
                article_ts=article_ts,
                market_resolved_at=resolved_at,
                category=category,
                bars_df=bars_df,
                prior_article_count=prior_count,
            )

            windows = compute_reaction_windows(
                article_ts=article_ts,
                timestamp_precision=str(prec),
                market_resolved_at=resolved_at,
                bars_df=bars_df,
                window_hours=window_hours,
            )

            output_rows.append({
                "article_id": article_id,
                "group_id": group_id,
                "market_id": market_id,
                "event_id": str(event_id) if event_id else "",
                "is_match": bool(is_match),
                "match_strength": float(match_strength),
                "directional_impact": int(di),
                "magnitude": float(mag),
                "news_type": str(news_type),
                "embedding_source": embedding_source,
                "canonical_ts": int(article_ts.timestamp()) if article_ts is not None else None,
                "market_resolved_at": resolved_at.isoformat() if resolved_at is not None else None,
                "end_at": (
                    pd.Timestamp(minfo["end_at"]).isoformat()
                    if minfo.get("end_at") and pd.notna(minfo.get("end_at"))
                    else None
                ),
                "strike_price": minfo.get("strike_price"),
                "strike_direction": minfo.get("strike_direction"),
                **chars,
                **windows,
            })

    out_df = pd.DataFrame(output_rows)
    # Joint monotone strike-ladder correction (novel_math_design.md Thread 2) —
    # adds y_logit_{Δ}h_ladder / ladder_n_members_used_{Δ}h columns. Separate
    # stage from reaction_windows/market_chars above: purely additive, does not
    # change any existing column.
    out_df = compute_ladder_adjusted_reactions(out_df, window_hours)
    out_path = ANALYSIS_DIR / "tuples.parquet"
    pq.write_table(pa.Table.from_pandas(out_df), out_path)
    log.info("tuples written", rows=len(out_df), path=str(out_path))

    for dh in window_hours:
        valid_col = f"valid_{dh}h"
        if valid_col in out_df.columns:
            n_valid = out_df[valid_col].sum()
            print(f"valid_{dh}h: {n_valid}/{len(out_df)} ({100*n_valid/max(len(out_df),1):.1f}%)")


if __name__ == "__main__":
    main()
