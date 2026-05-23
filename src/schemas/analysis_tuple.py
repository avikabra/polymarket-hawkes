from typing import Any

from src.schemas.market import Market
from src.schemas.news_event import NewsEvent
from src.schemas.trade import Trade


class AnalysisTuple(Market):
    trade_count: int
    trades: list[Trade]
    bars_1min: list[dict[str, Any]]
    news_event_count: int
    news_events: list[NewsEvent]
    hawkes_eligible_event_count: int
    has_full_text_pct: float
    passes_feasibility_gate: bool | None = None
