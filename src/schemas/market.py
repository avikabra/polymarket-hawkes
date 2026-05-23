from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Market(BaseModel):
    market_id: str
    slug: str
    question: str
    description: str
    category: str
    tags: list[str]
    created_at: datetime
    end_at: datetime
    resolved_at: datetime | None
    yes_token_id: str
    no_token_id: str
    resolved_outcome: Literal["YES", "NO", "INVALID"]
    total_volume_usdc: float
    market_type: Literal[
        "season_long", "championship", "playoff_series",
        "conference", "single_game", "other"
    ]
    parent_event_id: str | None
    is_primary_sample: bool
