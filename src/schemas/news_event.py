from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class NewsEvent(BaseModel):
    event_id: str
    market_id: str
    canonical_ts: datetime
    timestamp_precision: Literal["minute", "day"]
    included_in_hawkes_likelihood: bool
    directional_impact: Literal[-1, 0, 1]
    magnitude: float  # ∈ [0, 1]; modulates cross-excitation kernel φ_nt
    member_article_ids: list[str]
    member_count: int
    sources: list[str]

    @model_validator(mode="after")
    def _check_hawkes_eligibility(self) -> "NewsEvent":
        if self.included_in_hawkes_likelihood and self.timestamp_precision != "minute":
            raise ValueError(
                "included_in_hawkes_likelihood may only be True when "
                f"timestamp_precision == 'minute', got '{self.timestamp_precision}'"
            )
        return self
