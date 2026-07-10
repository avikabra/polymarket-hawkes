from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class NewsEvent(BaseModel):
    event_id: str
    market_id: str
    canonical_ts: datetime
    timestamp_precision: Literal["minute", "day"]
    member_article_ids: list[str]
    member_count: int
    sources: list[str]
    consensus_directional_impact: Literal[-1, 0, 1]
    dominant_news_type: str
