"""Rule-based verification of (market, article) candidate pairs.

Uses FAISS embedding_score for match_strength and a keyword list for
directional_impact. No API key required. Produces the same VerificationResult
schema as llm_verifier so downstream code is unchanged.
"""

from __future__ import annotations

import re

from src.matching._types import VerificationResult

# Words that suggest the YES outcome is more likely (bullish for market resolution)
_BULLISH = frozenset(
    "win wins won beat beats victory victories lead leads leading advance advances "
    "record records strong gains positive surge surges rise rises up upgrade".split()
)

# Words that suggest the NO outcome is more likely (bearish for market resolution)
_BEARISH = frozenset(
    "loss lose loses lost defeat defeats miss misses fall falls decline declines "
    "injury injured out suspension suspended weak negative drop drops down downgrade".split()
)

# Digits/stats suggest quantitative news
_QUANT_RE = re.compile(r"\b\d+[\d.,]*\b")


def verify_pair_rule(
    embedding_score: float,
    article_title: str,
    article_lede: str | None,
    *,
    match_threshold: float = 0.50,
) -> VerificationResult:
    """Return a VerificationResult derived from embedding score and keywords."""
    text = f"{article_title} {article_lede or ''}".lower()
    words = set(re.findall(r"[a-z]+", text))

    bullish_hits = words & _BULLISH
    bearish_hits = words & _BEARISH
    if bullish_hits and not bearish_hits:
        directional_impact = 1
    elif bearish_hits and not bullish_hits:
        directional_impact = -1
    else:
        directional_impact = 0

    news_type = "quantitative" if _QUANT_RE.search(text) else "qualitative"

    reasoning_parts = []
    if bullish_hits:
        reasoning_parts.append(f"bullish={sorted(bullish_hits)[:3]}")
    if bearish_hits:
        reasoning_parts.append(f"bearish={sorted(bearish_hits)[:3]}")
    reasoning = f"rule-based; score={embedding_score:.3f}; " + (
        "; ".join(reasoning_parts) if reasoning_parts else "no sentiment keywords"
    )

    return VerificationResult(
        is_match=embedding_score >= match_threshold,
        match_strength=round(embedding_score, 4),
        directional_impact=directional_impact,
        magnitude=round(embedding_score, 4),
        news_type=news_type,
        reasoning=reasoning,
    )
