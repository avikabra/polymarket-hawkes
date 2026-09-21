"""Open-weight LLM verification of (group, article) candidate pairs via an
OpenAI-compatible endpoint (vLLM / TGI / SGLang — whatever Yale's Bouchet HPC
cluster ends up exposing).

Mirrors llm_verifier.py's structure and VerificationResult output contract exactly,
swapping AsyncAnthropic for openai.AsyncOpenAI. This is Prof. Kelly's "small
open-weight LLM judge" stage, explicitly deferred until Bouchet access lands
(see reports/yale_cluster_request.md, reports/llm_judge_deferred.md).

HARD CONSTRAINT: no local LLM inference and no hosted-API pilot calls are permitted
in this session. This module is code-complete and exercised only via mocks in
tests/test_openweight_verifier.py — it is never actually invoked here.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import yaml
from openai import AsyncOpenAI, RateLimitError
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.matching._types import VerificationResult
from src.utils import get_logger

# Identical judging rubric to llm_verifier.py's Claude Haiku prompt — the two
# judges must be interchangeable outputs of the same task, not different tasks.
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

CONFIG_PATH = Path("config/openweight_llm.yaml")
CONFIG_TEMPLATE_PATH = Path("config/openweight_llm.yaml.template")

_log = get_logger(__name__)
_SEM = asyncio.Semaphore(8)

_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(RateLimitError),
    reraise=True,
)


def load_config() -> dict:
    """Load config/openweight_llm.yaml. Raises RuntimeError (pointing at the
    template) if it's missing — never falls back to a default base_url."""
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"{CONFIG_PATH} not found. Copy {CONFIG_TEMPLATE_PATH} to {CONFIG_PATH} and "
            "fill in base_url/model/api_key_env_var once Bouchet access lands "
            "(see reports/yale_cluster_request.md, reports/llm_judge_deferred.md)."
        )
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    missing = [k for k in ("base_url", "model", "api_key_env_var") if not cfg.get(k)]
    if missing:
        raise RuntimeError(
            f"{CONFIG_PATH} is missing required key(s) {missing} — see "
            f"{CONFIG_TEMPLATE_PATH} for the expected shape."
        )
    return cfg


def make_client(cfg: dict) -> AsyncOpenAI:
    """Build an AsyncOpenAI client from a loaded config dict. No default base_url —
    a missing api key raises RuntimeError rather than silently pointing at localhost."""
    api_key_env_var = cfg["api_key_env_var"]
    api_key = os.environ.get(api_key_env_var)
    if not api_key:
        raise RuntimeError(
            f"${api_key_env_var} not set (named by {CONFIG_PATH}'s api_key_env_var) — "
            "set it in .env before running with --openweight."
        )
    return AsyncOpenAI(base_url=cfg["base_url"], api_key=api_key)


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a string (handles markdown code fences)."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON object found in response: {text!r}")
    return json.loads(m.group())


async def verify_pair_openweight(
    client: AsyncOpenAI,
    model: str,
    group_id: str,
    group_text: str,
    article_id: str,
    article_title: str,
    article_lede: str | None,
) -> VerificationResult | None:
    """Return VerificationResult for one (group, article) pair, or None on persistent failure."""
    user_msg = (
        f"Market: {group_text}\n\n"
        f"Article title: {article_title}\n"
        f"Article lede: {article_lede or '(none)'}"
    )

    async def _call() -> VerificationResult:
        @retry(**_RETRY_KWARGS)
        async def _api_call() -> str:
            async with _SEM:
                resp = await client.chat.completions.create(
                    model=model,
                    max_tokens=256,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                )
            return resp.choices[0].message.content

        raw = await _api_call()
        return VerificationResult(**_extract_json(raw))

    # Try once; retry once on ValidationError (mirrors llm_verifier.py exactly).
    for attempt in range(2):
        try:
            return await _call()
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            if attempt == 0:
                _log.warning(
                    "malformed verifier response, retrying",
                    group_id=group_id, article_id=article_id, error=str(exc),
                )
                continue
            _log.error(
                "verifier failed after retry",
                group_id=group_id, article_id=article_id, error=str(exc),
            )
        except Exception as exc:
            _log.error(
                "verifier error",
                group_id=group_id, article_id=article_id, error=str(exc),
            )
            break

    return None
