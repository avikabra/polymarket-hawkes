"""LLM verification of (market, article) candidate pairs via Claude Haiku.

Output schema (VerificationResult) matches plan §0.6 / §4.3.
Runs 8 parallel async calls with exponential backoff on 429.
Malformed responses are retried once before being logged and skipped.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Literal

from anthropic import AsyncAnthropic, RateLimitError
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.utils import get_logger

_NEWS_TYPES = {"quantitative", "qualitative", "high_attention", "ambiguous"}

_SYSTEM_PROMPT = """You are a financial event classifier. For each (prediction market, news article) pair, decide whether the article is relevant to the market's resolution outcome.

Return ONLY a valid JSON object with exactly these fields:
{
  "is_match": <bool>,
  "match_strength": <float 0.0–1.0>,
  "directional_impact": <-1, 0, or 1>,
  "magnitude": <float 0.0–1.0>,
  "news_type": <"quantitative"|"qualitative"|"high_attention"|"ambiguous">,
  "reasoning": <string, max 80 words>
}

Definitions:
- is_match: true iff the article directly concerns the event the market resolves on.
- match_strength: confidence in is_match (0.5 = uncertain, 1.0 = certain).
- directional_impact: +1=article is bullish for the YES outcome, -1=bearish, 0=neutral/ambiguous.
- magnitude: 0.0–1.0 subjective salience — how market-moving is this likely to be.
- news_type: quantitative=has scores/stats/measurements; qualitative=analysis/opinion; high_attention=likely widely read; ambiguous=unclear implications.
- reasoning: brief justification."""


class VerificationResult(BaseModel):
    is_match: bool
    match_strength: float = Field(ge=0.0, le=1.0)
    directional_impact: Literal[-1, 0, 1]
    magnitude: float = Field(ge=0.0, le=1.0)
    news_type: Literal["quantitative", "qualitative", "high_attention", "ambiguous"]
    reasoning: str


_log = get_logger(__name__)
_SEM = asyncio.Semaphore(8)

_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a string (handles markdown code fences)."""
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find first {...}
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON object found in response: {text!r}")
    return json.loads(m.group())


async def verify_pair(
    client: AsyncAnthropic,
    market_id: str,
    market_question: str,
    article_id: str,
    article_title: str,
    article_lede: str | None,
) -> VerificationResult | None:
    """Return VerificationResult for one (market, article) pair, or None on persistent failure."""
    user_msg = (
        f"Market: {market_question}\n\n"
        f"Article title: {article_title}\n"
        f"Article lede: {article_lede or '(none)'}"
    )

    async def _call() -> VerificationResult:
        @retry(**_RETRY_KWARGS)
        async def _api_call() -> str:
            async with _SEM:
                resp = await client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=256,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                )
            return resp.content[0].text

        raw = await _api_call()
        return VerificationResult(**_extract_json(raw))

    # Try once; retry once on ValidationError
    for attempt in range(2):
        try:
            return await _call()
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            if attempt == 0:
                _log.warning(
                    "malformed verifier response, retrying",
                    market_id=market_id, article_id=article_id, error=str(exc),
                )
                continue
            _log.error(
                "verifier failed after retry",
                market_id=market_id, article_id=article_id, error=str(exc),
            )
        except Exception as exc:
            _log.error(
                "verifier error",
                market_id=market_id, article_id=article_id, error=str(exc),
            )
            break

    return None
