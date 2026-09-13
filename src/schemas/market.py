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
    contract_family: Literal["price_ladder", "market_cap_ladder", "valuation_ladder", "revenue_ladder", "other_ladder", "corporate_event", "other"] = "other"
    parent_event_id: str | None
    is_primary_sample: bool
    company_name: str | None = None
    ticker: str | None = None
    company_id: str = ""
    # strike_price/strike_direction/price_expiry_month hold the generic threshold value/direction/period for ANY ladder metric (price, valuation, revenue, market_cap), not only share price.
    strike_price: float | None = None
    strike_direction: Literal["above", "below"] | None = None
    price_expiry_month: str | None = None  # ISO "YYYY-MM"
    group_id: str = ""
    group_role: Literal["child", "standalone"] = "standalone"
    volume_1wk: float = 0.0
    volume_1mo: float = 0.0
