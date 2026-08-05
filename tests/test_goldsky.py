import math

from src.polymarket.trades import normalize_fill, price_to_log_odds

# Goldsky subgraph represents USDC as assetId "0", not the ERC-20 address.
# The fill id format is txHash_orderHash (no logIndex or blockNumber fields).
USDC = "0"
YES_TOKEN = "0xyes000000000000000000000000000000000000"
NO_TOKEN = "0xno0000000000000000000000000000000000000"

_YES_BUY_FILL = {
    "id": "0xaaaa1111_0xbbbb2222",
    "transactionHash": "0xaaaa1111",
    "timestamp": "1700000000",
    "makerAssetId": YES_TOKEN,     # maker sold YES tokens
    "takerAssetId": USDC,          # taker paid USDC
    "makerAmountFilled": "1000000",  # 1 YES token (6 dec)
    "takerAmountFilled": "600000",   # 0.6 USDC → price = 0.6
}

_NO_BUY_FILL = {
    **_YES_BUY_FILL,
    "id": "0xaaaa2222_0xcccc3333",
    "transactionHash": "0xaaaa2222",
    "makerAssetId": NO_TOKEN,      # maker sold NO tokens
    "takerAmountFilled": "400000", # 0.4 USDC → NO price = 0.4 → YES price = 0.6
}

_ZERO_FILL = {**_YES_BUY_FILL, "id": "0xaaaa3333_0xdddd4444", "transactionHash": "0xaaaa3333", "makerAmountFilled": "0"}


def test_normalize_yes_buy():
    trade = normalize_fill(_YES_BUY_FILL, market_id="mkt1", yes_token_id=YES_TOKEN)
    assert trade is not None
    assert trade.side == "YES_BUY"
    assert math.isfinite(trade.log_odds)
    assert abs(trade.price_raw - 0.6) < 1e-6


def test_normalize_no_fill_price_inverted():
    trade = normalize_fill(_NO_BUY_FILL, market_id="mkt1", yes_token_id=YES_TOKEN)
    assert trade is not None
    # NO price = 0.4 → YES price = 0.6; buying NO = YES_SELL
    assert trade.side == "YES_SELL"
    assert abs(trade.price_raw - 0.6) < 1e-6


def test_normalize_returns_none_for_zero_amount():
    result = normalize_fill(_ZERO_FILL, market_id="mkt1", yes_token_id=YES_TOKEN)
    assert result is None


def test_price_to_log_odds_half():
    assert abs(price_to_log_odds(0.5)) < 1e-9


def test_price_to_log_odds_clips_zero():
    assert price_to_log_odds(0.0) == price_to_log_odds(0.001)
