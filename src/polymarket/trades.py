import math

from src.schemas import Trade

USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174".lower()


def price_to_log_odds(price: float) -> float:
    p = max(0.001, min(0.999, price))
    return math.log(p / (1.0 - p))


def normalize_fill(raw: dict, market_id: str, yes_token_id: str) -> Trade | None:
    maker_asset = raw["makerAssetId"].lower()
    taker_asset = raw["takerAssetId"].lower()
    maker_amt = int(raw["makerAmountFilled"])
    taker_amt = int(raw["takerAmountFilled"])

    if maker_amt == 0 or taker_amt == 0:
        return None

    if taker_asset == USDC_ADDRESS:
        usdc_amt, token_amt, token_id = taker_amt, maker_amt, maker_asset
        taker_paid_usdc = True
    elif maker_asset == USDC_ADDRESS:
        usdc_amt, token_amt, token_id = maker_amt, taker_amt, taker_asset
        taker_paid_usdc = False
    else:
        return None

    # USDC and CTF tokens both use 6 decimals, so ratio is the raw probability
    raw_p = usdc_amt / token_amt
    is_yes = token_id == yes_token_id.lower()
    price_raw = max(0.001, min(0.999, raw_p if is_yes else 1.0 - raw_p))
    log_odds = math.log(price_raw / (1.0 - price_raw))

    # Side in YES terms: buying NO = selling YES, selling NO = buying YES
    if is_yes:
        side = "YES_BUY" if taker_paid_usdc else "YES_SELL"
    else:
        side = "YES_SELL" if taker_paid_usdc else "YES_BUY"

    return Trade(
        market_id=market_id,
        token_id=token_id,
        ts_s=int(raw["timestamp"]),
        log_index=int(raw["logIndex"]),
        price_raw=price_raw,
        log_odds=log_odds,
        size_usdc=usdc_amt / 1_000_000,
        side=side,
        tx_hash=raw["transactionHash"],
    )


def sort_trades(trades: list[Trade]) -> list[Trade]:
    return sorted(trades, key=lambda t: (t.ts_s, t.log_index))
