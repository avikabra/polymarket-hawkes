"""Joint (embedding + liquidity) verification of (group, article) candidate pairs.

Per novel_math_design.md Thread 1, "Formula (Q1, Option B)":
  match_quality_logit = w1 * logit(clip(embedding_score, eps, 1-eps)) + w2 * liquidity_z
  match_strength = sigmoid(match_quality_logit)

A log-odds combination of standardized text-similarity and liquidity signals.
Caveat (state in thesis text): this borrows the log-odds combination *form*, not
a literal probability model — logit(embedding_score) is a metaphor reuse of a
cosine similarity, not a real probability.

Produces the same VerificationResult schema as rule_verifier/llm_verifier so
downstream code (script 09's --joint path) is unchanged.
"""

from __future__ import annotations

import math

from src.matching._types import VerificationResult

# Matches this repo's own price_raw clipping convention (CLAUDE.md, src/polymarket/
# trades.py: `max(0.001, min(0.999, price))`) — applied here to embedding_score
# before logit so cosine similarities of exactly 0.0/1.0 don't produce +/-inf.
_CLIP_EPS = 0.001


def _logit(p: float) -> float:
    clipped = max(_CLIP_EPS, min(1.0 - _CLIP_EPS, p))
    return math.log(clipped / (1.0 - clipped))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def verify_pair_joint(
    embedding_score: float,
    liquidity_z: float,
    price_impact: float | None,
    w1: float = 1.0,
    w2: float = 1.0,
    *,
    match_threshold: float = 0.50,
) -> VerificationResult:
    """Return a VerificationResult combining embedding similarity and the
    liquidity signal (src/matching/liquidity_signal.py) in log-odds space.

    price_impact, if given, is a signed log-odds price move (positive = market
    moved toward YES); its sign informs directional_impact the same way
    rule_verifier.py's keyword hits inform it there. liquidity_signal.py's
    compute_liquidity_response currently reports max |price_impact| (unsigned,
    aggregated across a group's member markets) — sign is lost at that
    aggregation step, so a caller wiring that output through this function gets
    directional_impact=0 until/unless a signed per-market variant is wired in.
    That's a design gap in the plan doc, not an oversight here — flagging it.
    """
    match_quality_logit = w1 * _logit(embedding_score) + w2 * liquidity_z
    match_strength = _sigmoid(match_quality_logit)
    is_match = match_strength >= match_threshold

    if price_impact is None or price_impact == 0:
        directional_impact = 0
    else:
        directional_impact = 1 if price_impact > 0 else -1

    # No article text is available to this verifier (unlike rule_verifier), so
    # news_type can't be classified from keywords/digits — "ambiguous" is the
    # honest default rather than guessing a class. Not specified in the plan doc.
    news_type = "ambiguous"

    # Mirrors rule_verifier.py's own choice of reusing its primary score as
    # magnitude (`magnitude=round(embedding_score, 4)`) — here the primary score
    # is match_strength, the joint quantity this verifier actually judges on.
    # Not specified in the plan doc.
    magnitude = round(match_strength, 4)

    reasoning = (
        f"joint: embedding_score={embedding_score:.3f}, liquidity_z={liquidity_z:.3f}, "
        f"price_impact={price_impact}, w1={w1}, w2={w2}, "
        f"match_quality_logit={match_quality_logit:.3f}, match_strength={match_strength:.3f}"
    )

    return VerificationResult(
        is_match=is_match,
        match_strength=round(match_strength, 4),
        directional_impact=directional_impact,
        magnitude=magnitude,
        news_type=news_type,
        reasoning=reasoning,
    )
