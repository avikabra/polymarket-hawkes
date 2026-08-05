import math

from src.schemas import Trade

# The Goldsky orderbook subgraph represents USDC as assetId "0", not the ERC-20 address.
_USDC_ASSET_ID = "0"


def price_to_log_odds(price: float) -> float:
    p = max(0.001, min(0.999, price))
    return math.log(p / (1.0 - p))


def _order_hash_to_log_index(fill_id: str) -> int:
    """Derive a stable integer tiebreaker from the fill id (txHash_orderHash).

    The subgraph id has no logIndex field. We take the last 8 hex chars of the
    orderHash part as an unsigned 32-bit integer — stable, bounded, and unique
    enough to break ties within the same second for sort_trades.
    """
    parts = fill_id.split("_", 1)
    order_hash = parts[1] if len(parts) == 2 else fill_id
    # Strip leading "0x" if present, take last 8 hex digits
    hex_str = order_hash[2:] if order_hash.startswith("0x") else order_hash
    hex_part = hex_str[-8:] or "0"
    return int(hex_part, 16)


def normalize_fill(raw: dict, market_id: str, yes_token_id: str) -> Trade | None:
    maker_asset = raw["makerAssetId"]
    taker_asset = raw["takerAssetId"]
    maker_amt = int(raw["makerAmountFilled"])
    taker_amt = int(raw["takerAmountFilled"])

    if maker_amt == 0 or taker_amt == 0:
        return None

    if taker_asset == _USDC_ASSET_ID:
        usdc_amt, token_amt, token_id = taker_amt, maker_amt, maker_asset
        taker_paid_usdc = True
    elif maker_asset == _USDC_ASSET_ID:
        usdc_amt, token_amt, token_id = maker_amt, taker_amt, taker_asset
        taker_paid_usdc = False
    else:
        return None

    # USDC and CTF tokens both use 6 decimals, so ratio is the raw probability
    raw_p = usdc_amt / token_amt
    is_yes = token_id == yes_token_id
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
        log_index=_order_hash_to_log_index(raw["id"]),
        price_raw=price_raw,
        log_odds=log_odds,
        size_usdc=usdc_amt / 1_000_000,
        side=side,
        tx_hash=raw["transactionHash"],
    )


def sort_trades(trades: list[Trade]) -> list[Trade]:
    return sorted(trades, key=lambda t: (t.ts_s, t.log_index))
