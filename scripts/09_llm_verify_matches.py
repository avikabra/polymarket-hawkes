"""Script 09: Verify (group, article) candidate pairs.

Default: rule-based (embedding score + keyword sentiment, no API key needed) — the
ONLY judge this script actually invokes in the Weeks 7-9 session (hard constraint:
no local LLM inference, no hosted-API pilot calls).
--llm uses Claude Haiku (requires ANTHROPIC_API_KEY in .env) — kept for compatibility,
not invoked here.
--openweight uses an OpenAI-compatible open-weight endpoint (see
src/matching/openweight_verifier.py) for the Bouchet HPC deferred-judge stage — code-
complete, mock-tested only, not invoked here (see reports/llm_judge_deferred.md).
--joint uses the liquidity-validated joint score (novel_math_design.md Thread 1:
embedding_score + abnormal-volume z-score in log-odds space, src/matching/joint_verifier.py)
— runs alongside (not instead of) the rule-based pass; requires data/polymarket/bars_1min.

Writes results incrementally to the verifications table (resume-safe),
then writes _VERIFIED_SUCCESS.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from dotenv import load_dotenv

from src.matching.embedder import _build_group_text
from src.news.normalizer import build_matching_text_corpus
from src.utils import assert_covers, get_logger

load_dotenv()

DB_PATH = Path("data/matches/matches.db")
MATCHES_DIR = Path("data/matches")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")
CONTRACT_GROUPS_PATH = Path("data/polymarket/contract_groups.parquet")

# Provisional — see final report / reports/llm_judge_deferred.md. Not to be changed
# without flagging: 0.65 was chosen to mirror the "high confidence" cut a human
# reviewer would apply, not fitted against any labeled set (none exists yet).
_HIGH_CONFIDENCE_THRESHOLD = 0.65

log = get_logger(__name__)


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Add news_type/review_status columns if the DB predates them in the schema."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(verifications)")}
    if "news_type" not in cols:
        conn.execute("ALTER TABLE verifications ADD COLUMN news_type TEXT")
    if "review_status" not in cols:
        conn.execute("ALTER TABLE verifications ADD COLUMN review_status TEXT")
    conn.commit()


def _load_article_meta() -> dict[str, dict]:
    """Build article_id → {title, lede, entities} lookup from the normalized
    matching-text corpus.

    Uses build_matching_text_corpus (same chain script 07 embeds) rather than a raw
    parquet concat — GDELT rows there get a real synthetic entity/theme title instead
    of the placeholder title==url string. Before this fix, verify_pair_rule's keyword
    scoring ran against a bare URL for every GDELT article, making its
    directional_impact/news_type output nearly meaningless.

    `entities` (added 2026-10-05) feeds --joint's entity-grounding term — see
    src/matching/joint_verifier.py's extension note.
    """
    df = build_matching_text_corpus(str(GDELT_DIR), str(FEEDS_DIR))
    if df.empty:
        return {}
    meta: dict[str, dict] = {}
    for _, row in df.iterrows():
        meta[row["article_id"]] = {
            "title": str(row.get("title", "")),
            "lede": row.get("lede") or None,
            "entities": list(row.get("entities") or []),
        }
    return meta


def _load_group_texts(contract_groups_df: pd.DataFrame, universe_df: pd.DataFrame) -> dict[str, str]:
    """group_id -> matching text, via the same builder script 07 embeds with (A4)."""
    universe_lookup = {str(row["market_id"]): row for row in universe_df.to_dict("records")}
    return {
        str(row["group_id"]): _build_group_text(row, universe_lookup)
        for row in contract_groups_df.to_dict("records")
    }


def _review_status(is_match: bool, match_strength: float) -> str | None:
    if not is_match:
        return None
    return "high_confidence" if match_strength >= _HIGH_CONFIDENCE_THRESHOLD else "low_confidence"


def _run_rule_based(conn: sqlite3.Connection, todo: list[tuple], article_meta: dict) -> tuple[int, int]:
    """Verify all pairs with rule-based classifier. Returns (verified, skipped)."""
    from src.matching.rule_verifier import verify_pair_rule

    verified = 0
    skipped = 0
    batch_size = 200

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        rows = []
        now_ts = datetime.now(timezone.utc).isoformat()
        for group_id, article_id, embedding_score in batch:
            meta = article_meta.get(article_id, {})
            result = verify_pair_rule(
                embedding_score=embedding_score,
                article_title=meta.get("title", ""),
                article_lede=meta.get("lede"),
            )
            rows.append((
                group_id, article_id,
                int(result.is_match), result.match_strength,
                result.directional_impact, result.magnitude,
                result.news_type, result.reasoning,
                _review_status(result.is_match, result.match_strength), now_ts,
            ))
            verified += 1

        conn.executemany(
            "INSERT OR IGNORE INTO verifications "
            "(group_id, article_id, is_match, match_strength, directional_impact, "
            "magnitude, news_type, reasoning, review_status, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        log.info("rule verification progress", done=min(i + batch_size, len(todo)), total=len(todo))

    return verified, skipped


async def _run_llm(conn: sqlite3.Connection, todo: list[tuple], article_meta: dict, group_texts: dict) -> tuple[int, int]:
    """Verify all pairs with Claude Haiku. Returns (verified, skipped). Not invoked this session."""
    from anthropic import AsyncAnthropic
    from src.matching.llm_verifier import verify_pair

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set in .env — cannot use --llm mode.")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key)
    batch_size = 50
    verified = 0
    skipped = 0

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        tasks = []
        for group_id, article_id, _score in batch:
            group_text = group_texts.get(group_id, "")
            meta = article_meta.get(article_id, {})
            tasks.append(verify_pair(
                client=client,
                market_id=group_id,
                market_question=group_text,
                article_id=article_id,
                article_title=meta.get("title", ""),
                article_lede=meta.get("lede"),
            ))

        results = await asyncio.gather(*tasks)
        now_ts = datetime.now(timezone.utc).isoformat()

        rows = []
        for (group_id, article_id, _score), result in zip(batch, results):
            if result is None:
                skipped += 1
                continue
            rows.append((
                group_id, article_id,
                int(result.is_match), result.match_strength,
                result.directional_impact, result.magnitude,
                result.news_type, result.reasoning,
                _review_status(result.is_match, result.match_strength), now_ts,
            ))
            verified += 1

        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO verifications "
                "(group_id, article_id, is_match, match_strength, directional_impact, "
                "magnitude, news_type, reasoning, review_status, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()

        log.info("LLM verification progress", done=min(i + batch_size, len(todo)), total=len(todo))

    return verified, skipped


def _run_joint(
    conn: sqlite3.Connection,
    verified_pairs: set[tuple[str, str]],
    group_members: dict[str, list[str]],
    resolved_at_map: dict[str, pd.Timestamp | None],
    article_meta: dict[str, dict],
    group_aliases: dict[str, list[str]],
) -> tuple[int, int]:
    """Verify all pairs with the joint (embedding + liquidity + entity-grounding)
    score (novel_math_design.md Thread 1, entity term added 2026-10-05). Returns
    (verified, skipped).

    A group with no member markets in contract_groups.parquet is skipped (counted
    in `skipped`) — that's a data-integrity gap, distinct from a group whose
    members simply have no real bars data, which compute_liquidity_response
    already handles gracefully (empty bars -> volume_z=0.0, price_impact=None;
    see src/utils/bars_io.py's load_bars empty-frame fallback and
    liquidity_signal.py's `if not df.empty` filtering), so that case is NOT
    skipped here — it still gets verified with liquidity_z=0.
    """
    from src.matching.joint_scoring import (
        group_resolved_at,
        load_group_member_bars,
        parse_article_ts,
        score_pair_joint,
    )

    candidates = conn.execute(
        "SELECT group_id, article_id, embedding_score, article_published_at, timestamp_precision "
        "FROM candidates"
    ).fetchall()
    todo = [row for row in candidates if (row[0], row[1]) not in verified_pairs]
    log.info("joint verification candidates", total=len(candidates), remaining=len(todo))

    verified = 0
    skipped = 0
    batch_size = 200

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        rows = []
        now_ts = datetime.now(timezone.utc).isoformat()
        for group_id, article_id, embedding_score, pub_at, prec in batch:
            group_id = str(group_id)
            member_ids = group_members.get(group_id, [])
            if not member_ids:
                skipped += 1
                continue

            member_bars = load_group_member_bars(member_ids)
            article_ts = parse_article_ts(pub_at)
            resolved_at = group_resolved_at(member_ids, resolved_at_map)
            entities = article_meta.get(article_id, {}).get("entities", [])
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
            rows.append((
                group_id, article_id,
                int(result.is_match), result.match_strength,
                result.directional_impact, result.magnitude,
                result.news_type, result.reasoning,
                _review_status(result.is_match, result.match_strength), now_ts,
            ))
            verified += 1

        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO verifications "
                "(group_id, article_id, is_match, match_strength, directional_impact, "
                "magnitude, news_type, reasoning, review_status, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()
        log.info("joint verification progress", done=min(i + batch_size, len(todo)), total=len(todo))

    return verified, skipped


async def _run_openweight(
    conn: sqlite3.Connection, todo: list[tuple], article_meta: dict, group_texts: dict,
    only_low_confidence: bool = False,
) -> tuple[int, int]:
    """Verify all pairs with an open-weight LLM judge (Bouchet HPC, OpenAI-compatible
    endpoint). Not invoked this session — see reports/llm_judge_deferred.md. Raises
    RuntimeError (pointing at config/openweight_llm.yaml.template) if unconfigured.
    """
    from src.matching.openweight_verifier import load_config, make_client, verify_pair_openweight

    cfg = load_config()
    client = make_client(cfg)
    model = cfg["model"]
    batch_size = 50
    verified = 0
    skipped = 0

    if only_low_confidence:
        # Re-verify existing low_confidence rows — these are already in the
        # verifications table, so they're NOT in `todo` (which the caller built
        # from *unverified* candidates only). Build this list independently by
        # joining low_confidence verifications back to their candidate rows.
        todo = conn.execute(
            "SELECT c.group_id, c.article_id, c.embedding_score "
            "FROM verifications v JOIN candidates c "
            "ON v.group_id = c.group_id AND v.article_id = c.article_id "
            "WHERE v.review_status = 'low_confidence'"
        ).fetchall()

    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        tasks = []
        for group_id, article_id, _score in batch:
            group_text = group_texts.get(group_id, "")
            meta = article_meta.get(article_id, {})
            tasks.append(verify_pair_openweight(
                client=client,
                model=model,
                group_id=group_id,
                group_text=group_text,
                article_id=article_id,
                article_title=meta.get("title", ""),
                article_lede=meta.get("lede"),
            ))

        results = await asyncio.gather(*tasks)
        now_ts = datetime.now(timezone.utc).isoformat()

        rows = []
        for (group_id, article_id, _score), result in zip(batch, results):
            if result is None:
                skipped += 1
                continue
            rows.append((
                group_id, article_id,
                int(result.is_match), result.match_strength,
                result.directional_impact, result.magnitude,
                result.news_type, result.reasoning,
                _review_status(result.is_match, result.match_strength), now_ts,
            ))
            verified += 1

        if rows:
            conn.executemany(
                "INSERT OR REPLACE INTO verifications "
                "(group_id, article_id, is_match, match_strength, directional_impact, "
                "magnitude, news_type, reasoning, review_status, verified_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()

        log.info("open-weight verification progress", done=min(i + batch_size, len(todo)), total=len(todo))

    return verified, skipped


def _print_match_strength_histogram(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT match_strength FROM verifications WHERE is_match=1").fetchall()
    if not rows:
        print("match_strength histogram: no is_match=1 rows")
        return
    buckets = Counter()
    for (score,) in rows:
        bucket = min(int((score or 0.0) * 10), 9)
        buckets[bucket] += 1
    print("match_strength histogram (is_match=1 only):")
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        print(f"  [{lo:.1f}, {hi:.1f}): {buckets.get(b, 0)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true", help="Use Claude Haiku (requires ANTHROPIC_API_KEY)")
    parser.add_argument(
        "--openweight", action="store_true",
        help="Use the open-weight judge (config/openweight_llm.yaml) — Bouchet HPC only, "
             "not invoked in this session. See reports/llm_judge_deferred.md.",
    )
    parser.add_argument(
        "--only-low-confidence", action="store_true",
        help="With --openweight, re-verify only review_status='low_confidence' rows "
             "(cheaper — targets exactly what the rule-based pass couldn't resolve).",
    )
    parser.add_argument(
        "--joint", action="store_true",
        help="Use the liquidity-validated joint score (novel_math_design.md Thread 1) "
             "instead of the rule-based verifier. Requires data/polymarket/bars_1min.",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print("No matches.db found — run script 08 first.")
        return

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
    group_texts = _load_group_texts(contract_groups_df, universe_df)

    article_meta = _load_article_meta()

    conn = sqlite3.connect(DB_PATH)
    _migrate_db(conn)

    verified_pairs = set(
        conn.execute("SELECT group_id, article_id FROM verifications").fetchall()
    )
    # Include embedding_score so rule-based path can use it directly
    candidates = conn.execute(
        "SELECT group_id, article_id, embedding_score FROM candidates"
    ).fetchall()
    todo = [(g, a, s) for g, a, s in candidates if (g, a) not in verified_pairs]
    log.info("candidates to verify", total=len(candidates), remaining=len(todo))

    if args.joint:
        log.info("using joint (embedding + liquidity) verifier")
        from src.matching.joint_scoring import (
            group_company_aliases_map,
            group_member_map,
            market_resolved_at_map,
        )

        group_members = group_member_map(contract_groups_df)
        resolved_at_map = market_resolved_at_map(universe_df)
        group_aliases = group_company_aliases_map(contract_groups_df)
        verified, skipped = _run_joint(
            conn, verified_pairs, group_members, resolved_at_map, article_meta, group_aliases,
        )
    elif args.openweight:
        log.info("using open-weight verifier (Bouchet HPC)")
        verified, skipped = await _run_openweight(
            conn, todo, article_meta, group_texts, only_low_confidence=args.only_low_confidence,
        )
    elif args.llm:
        log.info("using LLM verifier (Claude Haiku)")
        verified, skipped = await _run_llm(conn, todo, article_meta, group_texts)
    else:
        log.info("using rule-based verifier")
        verified, skipped = _run_rule_based(conn, todo, article_meta)

    MATCHES_DIR.mkdir(parents=True, exist_ok=True)
    (MATCHES_DIR / "_VERIFIED_SUCCESS").touch()

    print(f"Verified:  {verified}")
    print(f"Skipped:   {skipped}")
    _print_match_strength_histogram(conn)
    conn.close()
    print("Run script 10 (dedup) next.")


if __name__ == "__main__":
    asyncio.run(main())
