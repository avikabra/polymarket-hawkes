from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Article(BaseModel):
    article_id: str  # sha256 of url — computed by caller
    source: str
    url: str
    published_at: datetime | None
    timestamp_precision: Literal["minute", "day", "unknown"]
    title: str
    lede: str | None
    body_text: str | None
    text_available: bool
    entities: list[str]
    themes: list[str]  # GDELT GKG themes; empty for non-GDELT sources
    raw_metadata_json: str
