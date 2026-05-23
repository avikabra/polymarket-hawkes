import math
from collections import defaultdict

from src.schemas import Trade


def resample_to_1min(
    trades: list[Trade],
    market_open_ts: int,
    market_close_ts: int,
) -> list[dict]:
    open_min = (market_open_ts // 60) * 60
    n_minutes = math.ceil((market_close_ts - open_min) / 60)
    minutes = [open_min + i * 60 for i in range(max(1, n_minutes))]

    if not trades:
        return [
            {"ts_min": m, "open_lo": 0.0, "high_lo": 0.0, "low_lo": 0.0,
             "close_lo": 0.0, "volume_usdc": 0.0, "trade_count": 0}
            for m in minutes
        ]

    minute_trades: dict[int, list[Trade]] = defaultdict(list)
    for t in trades:
        minute_trades[(t.ts_s // 60) * 60].append(t)

    # Backward-fill pre-trade minutes with the first observed log-odds
    prev_close = trades[0].log_odds

    bars = []
    for m in minutes:
        mt = minute_trades.get(m)
        if mt:
            lo_vals = [t.log_odds for t in mt]
            bar = {
                "ts_min": m,
                "open_lo": lo_vals[0],
                "high_lo": max(lo_vals),
                "low_lo": min(lo_vals),
                "close_lo": lo_vals[-1],
                "volume_usdc": sum(t.size_usdc for t in mt),
                "trade_count": len(mt),
            }
            prev_close = bar["close_lo"]
        else:
            bar = {
                "ts_min": m,
                "open_lo": prev_close,
                "high_lo": prev_close,
                "low_lo": prev_close,
                "close_lo": prev_close,
                "volume_usdc": 0.0,
                "trade_count": 0,
            }
        bars.append(bar)

    return bars
