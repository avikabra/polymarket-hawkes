from typing import Literal

from pydantic import BaseModel


class VerifiedArticle(BaseModel):
    """Per-article analysis record — the primary unit of analysis in D4."""

    article_id: str
    market_id: str
    event_id: str  # cluster ID from dedup (script 10)

    # LLM verifier output
    is_match: bool
    match_strength: float  # ∈ [0, 1]
    directional_impact: Literal[-1, 0, 1]  # +1=bullish YES, -1=bearish, 0=neutral
    magnitude: float  # ∈ [0, 1]; salience label (not a model input)
    news_type: Literal["quantitative", "qualitative", "high_attention", "ambiguous"]
    embedding_source: Literal["full_text", "headline_only"]

    # Market characteristics — populated by script 12 (assembly)
    price_at_article: float | None = None  # logit(P_{k,t_i})
    time_to_resolution_days: float | None = None
    volume_24h_usdc: float | None = None
    prior_article_count: int | None = None
    category: str | None = None  # "nfl" | "nba" | "politics" | "geopolitics"

    # Reaction windows — populated by script 12
    y_logit_1h: float | None = None
    y_logit_6h: float | None = None
    y_logit_24h: float | None = None
    valid_1h: bool = False
    valid_6h: bool = False
    valid_24h: bool = False
