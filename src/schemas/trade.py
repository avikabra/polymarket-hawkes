import math
from typing import Literal

from pydantic import BaseModel, model_validator


class Trade(BaseModel):
    market_id: str
    token_id: str
    ts_s: int
    log_index: int
    price_raw: float
    log_odds: float
    size_usdc: float
    side: Literal["YES_BUY", "YES_SELL"]
    tx_hash: str

    @model_validator(mode="after")
    def _check_price_and_log_odds(self) -> "Trade":
        if not (0.0 < self.price_raw < 1.0):
            raise ValueError(f"price_raw must be in open interval (0,1), got {self.price_raw}")
        expected = math.log(self.price_raw / (1.0 - self.price_raw))
        if abs(self.log_odds - expected) > 1e-6:
            raise ValueError(
                f"log_odds {self.log_odds} inconsistent with price_raw {self.price_raw} "
                f"(expected {expected:.8f})"
            )
        return self
