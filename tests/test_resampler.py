import math

import pytest

from src.polymarket.resampler import resample_to_1min
from src.schemas import Trade


def _trade(ts_s: int, price: float, size_usdc: float = 100.0) -> Trade:
    p = max(0.001, min(0.999, price))
    return Trade(
        market_id="mkt1",
        token_id="tok1",
        ts_s=ts_s,
        log_index=0,
        price_raw=p,
        log_odds=math.log(p / (1.0 - p)),
        size_usdc=size_usdc,
        side="YES_BUY",
        tx_hash="0xtx",
    )


def test_3_trades_in_one_minute():
    trades = [_trade(10, 0.5, 100), _trade(20, 0.6, 200), _trade(30, 0.7, 150)]
    bars = resample_to_1min(trades, market_open_ts=0, market_close_ts=60)
    assert len(bars) == 1
    bar = bars[0]
    assert bar["ts_min"] == 0
    assert bar["trade_count"] == 3
    assert abs(bar["volume_usdc"] - 450.0) < 1e-6
    assert abs(bar["open_lo"] - math.log(0.5 / 0.5)) < 1e-6
    assert abs(bar["close_lo"] - math.log(0.7 / 0.3)) < 1e-6
    assert abs(bar["high_lo"] - math.log(0.7 / 0.3)) < 1e-6
    assert abs(bar["low_lo"] - math.log(0.5 / 0.5)) < 1e-6


def test_no_trades_5_minutes_carry_forward():
    trades = [_trade(30, 0.6)]
    bars = resample_to_1min(trades, market_open_ts=0, market_close_ts=6 * 60)
    assert len(bars) == 6
    assert bars[0]["trade_count"] == 1
    lo_06 = math.log(0.6 / 0.4)
    for bar in bars[1:]:
        assert bar["trade_count"] == 0
        assert bar["volume_usdc"] == 0.0
        assert abs(bar["close_lo"] - lo_06) < 1e-6


def test_empty_trade_list():
    bars = resample_to_1min([], market_open_ts=0, market_close_ts=5 * 60)
    assert len(bars) == 5
    for bar in bars:
        assert bar["trade_count"] == 0
        assert bar["close_lo"] == 0.0


def test_bar_prices_are_log_odds_not_price_raw():
    trades = [_trade(30, 0.75)]
    bars = resample_to_1min(trades, market_open_ts=0, market_close_ts=60)
    assert len(bars) == 1
    bar = bars[0]
    # log_odds(0.75) = log(3) ≈ 1.0986, not 0.75
    assert abs(bar["close_lo"] - math.log(3)) < 1e-4
    assert bar["close_lo"] != pytest.approx(0.75)
