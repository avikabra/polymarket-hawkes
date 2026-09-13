"""Tests for src/polymarket/company_filter.py."""

from datetime import datetime, timezone

from src.polymarket.company_filter import classify_company_contract, extract_strike_fields


# ─────────────────────────────────────────────────────────────────────────────
# classify_company_contract — price_ladder (formerly "monthly_strike")
# ─────────────────────────────────────────────────────────────────────────────

def test_price_ladder_ticker_above():
    result = classify_company_contract(
        {"question": "Will NVDA close above $500 by end of January 2025?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"
    assert result["company_name"] == "Nvidia"
    assert result["ticker"] == "NVDA"
    assert result["company_id"] == "nvidia"


def test_price_ladder_name_below():
    result = classify_company_contract(
        {"question": "Will Tesla close below $200 end of March 2025?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"
    assert result["company_name"] == "Tesla"


def test_price_ladder_reach_dollar():
    result = classify_company_contract(
        {"question": "Will NVDA close above $190 end of July 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"


def test_price_ladder_spec_example():
    result = classify_company_contract(
        {"question": "Will NVDA close above $190 end of July?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"


# ─────────────────────────────────────────────────────────────────────────────
# classify_company_contract — market_cap_ladder
# ─────────────────────────────────────────────────────────────────────────────

def test_market_cap_ladder_nvidia():
    result = classify_company_contract(
        {"question": "Will NVIDIA's market cap exceed $4T by Aug 31?"}
    )
    assert result is not None
    assert result["contract_family"] == "market_cap_ladder"
    assert result["ladder_metric"] == "market_cap"
    assert result["company_name"] == "Nvidia"


def test_market_cap_ladder_capitalization_spelling():
    result = classify_company_contract(
        {"question": "Will Apple's market capitalization reach $4T by end of 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "market_cap_ladder"
    assert result["ladder_metric"] == "market_cap"


def test_market_cap_no_threshold_is_corporate_event():
    # "largest company by market cap" with no $ threshold → corporate_event or None,
    # NOT a ladder. "market cap" alone is in _CORP_EVENT_PAT so expect corporate_event.
    result = classify_company_contract(
        {"question": "Will Apple be the largest company by market cap in 2026?"}
    )
    # No numeric threshold → not a ladder; "market cap" is a corp signal → corporate_event
    assert result is None or result["contract_family"] == "corporate_event"


# ─────────────────────────────────────────────────────────────────────────────
# classify_company_contract — valuation_ladder
# ─────────────────────────────────────────────────────────────────────────────

def test_valuation_ladder_databricks():
    result = classify_company_contract(
        {"question": "Will Databricks' valuation hit $250B by June 30 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "valuation_ladder"
    assert result["ladder_metric"] == "valuation"
    assert result["company_name"] == "Databricks"


def test_valuation_ladder_stripe():
    result = classify_company_contract(
        {"question": "Will Stripe's valuation exceed $100B by end of 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "valuation_ladder"
    assert result["ladder_metric"] == "valuation"


def test_valuation_ladder_openai():
    result = classify_company_contract(
        {"question": "Will OpenAI be valued at $300B by mid-2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "valuation_ladder"
    assert result["ladder_metric"] == "valuation"


# ─────────────────────────────────────────────────────────────────────────────
# classify_company_contract — revenue_ladder
# ─────────────────────────────────────────────────────────────────────────────

def test_revenue_ladder_nvidia_data_center():
    result = classify_company_contract(
        {"question": "Will NVIDIA data center revenue be above $80B in FY26?"}
    )
    assert result is not None
    assert result["contract_family"] == "revenue_ladder"
    assert result["ladder_metric"] == "revenue"
    assert result["company_name"] == "Nvidia"


def test_revenue_ladder_airbnb_gross_bookings():
    result = classify_company_contract(
        {"question": "Will Airbnb Q2 gross booking value be above $26.4B?"}
    )
    assert result is not None
    assert result["contract_family"] == "revenue_ladder"
    assert result["ladder_metric"] == "revenue"
    assert result["company_name"] == "Airbnb"


def test_revenue_ladder_gross_bookings_variant():
    result = classify_company_contract(
        {"question": "Will Airbnb Q2 gross bookings be above $26.4B?"}
    )
    assert result is not None
    assert result["contract_family"] == "revenue_ladder"
    assert result["ladder_metric"] == "revenue"


def test_revenue_ladder_sales():
    result = classify_company_contract(
        {"question": "Will Apple annual sales exceed $500B in FY2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "revenue_ladder"
    assert result["ladder_metric"] == "revenue"


# ─────────────────────────────────────────────────────────────────────────────
# classify_company_contract — corporate_event (unchanged behavior)
# ─────────────────────────────────────────────────────────────────────────────

def test_corporate_event_earnings():
    result = classify_company_contract(
        {"question": "Will Microsoft beat earnings expectations in Q3 2025?"}
    )
    assert result is not None
    assert result["contract_family"] == "corporate_event"
    assert result["ladder_metric"] is None
    assert result["company_name"] == "Microsoft"


def test_corporate_event_ceo_change():
    result = classify_company_contract(
        {"question": "Will Apple's CEO resign by end of 2025?"}
    )
    assert result is not None
    assert result["contract_family"] == "corporate_event"
    assert result["ladder_metric"] is None


def test_corporate_event_acquisition():
    result = classify_company_contract(
        {"question": "Will Qualcomm acquire Intel?"}
    )
    assert result is not None
    assert result["contract_family"] == "corporate_event"
    assert result["ladder_metric"] is None


def test_corporate_event_google_acquisition():
    result = classify_company_contract(
        {"question": "Will Google acquire a major AI startup in 2025?"}
    )
    assert result is not None
    assert result["contract_family"] == "corporate_event"


def test_corporate_event_ipo():
    result = classify_company_contract(
        {"question": "Will Stripe go public (IPO) before 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "corporate_event"
    assert result["ladder_metric"] is None
    assert result["company_name"] == "Stripe"


def test_company_id_slug_private_company():
    result = classify_company_contract(
        {"question": "Will Anthropic complete its IPO by end of 2025?"}
    )
    assert result is not None
    assert result["company_id"] == "anthropic"
    assert result["ticker"] is None


# ─────────────────────────────────────────────────────────────────────────────
# classify_company_contract — EXCLUDE cases
# ─────────────────────────────────────────────────────────────────────────────

def test_sports_rejected():
    assert classify_company_contract(
        {"question": "Will the NBA Finals go to 7 games?"}
    ) is None


def test_sports_nfl_rejected():
    assert classify_company_contract(
        {"question": "Will the Chiefs win the Super Bowl?"}
    ) is None


def test_pure_crypto_rejected():
    assert classify_company_contract(
        {"question": "Will Bitcoin reach $100k?"}
    ) is None


def test_pure_crypto_eth_rejected():
    assert classify_company_contract(
        {"question": "Will Ethereum hit $5,000 by end of year?"}
    ) is None


def test_politics_rejected():
    assert classify_company_contract(
        {"question": "Will the Democrats win the 2026 election?"}
    ) is None


def test_politics_macro_fed_rejected():
    assert classify_company_contract(
        {"question": "Will the Fed cut interest rates in September?"}
    ) is None


def test_mstr_btc_rejected():
    assert classify_company_contract(
        {"question": "Will MicroStrategy stock follow Bitcoin above $100k?"}
    ) is None


def test_mstr_btc_reverse_order_rejected():
    assert classify_company_contract(
        {"question": "Will Bitcoin reach $150k before MSTR hits $1000?"}
    ) is None


def test_ai_leadership_rejected():
    assert classify_company_contract(
        {"question": "Will OpenAI have the best AI model by year end?"}
    ) is None


def test_ai_leadership_beat_claude_rejected():
    assert classify_company_contract(
        {"question": "Will Gemini outperform Claude by end of 2025?"}
    ) is None


def test_ai_leadership_frontier_rejected():
    assert classify_company_contract(
        {"question": "Which company will have the leading AI model in 2025?"}
    ) is None


def test_commodity_gold_rejected():
    assert classify_company_contract(
        {"question": "Will gold reach $3,000 per ounce?"}
    ) is None


def test_commodity_sp500_rejected():
    assert classify_company_contract(
        {"question": "Will the S&P 500 hit 6,000 by end of year?"}
    ) is None


def test_commodity_oil_rejected():
    assert classify_company_contract(
        {"question": "Will crude oil prices exceed $100 per barrel?"}
    ) is None


def test_no_company_match_rejected():
    assert classify_company_contract(
        {"question": "Will the housing market crash in 2025?"}
    ) is None


def test_no_family_match_rejected():
    # Company present but no strike or corporate-event signal
    assert classify_company_contract(
        {"question": "Will Apple remain popular in 2025?"}
    ) is None


# ─────────────────────────────────────────────────────────────────────────────
# MSTR without BTC — should NOT be excluded (pure earnings question)
# ─────────────────────────────────────────────────────────────────────────────

def test_mstr_earnings_without_btc_accepted():
    result = classify_company_contract(
        {"question": "Will MicroStrategy beat earnings expectations in Q4 2025?"}
    )
    assert result is not None
    assert result["contract_family"] == "corporate_event"
    assert result["company_name"] == "MicroStrategy"


# ─────────────────────────────────────────────────────────────────────────────
# extract_strike_fields — basic cases (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def test_strike_price_parsed():
    sf = extract_strike_fields("Will NVDA close above $500 by end of January 2025?")
    assert sf["strike_price"] == 500.0


def test_strike_direction_above():
    sf = extract_strike_fields("Will NVDA close above $500 by end of January 2025?")
    assert sf["strike_direction"] == "above"


def test_strike_direction_below():
    sf = extract_strike_fields("Will Tesla close below $200 end of March 2025?")
    assert sf["strike_direction"] == "below"


def test_expiry_month_with_year():
    sf = extract_strike_fields("Will NVDA close above $500 by end of January 2025?")
    assert sf["price_expiry_month"] == "2025-01"


def test_expiry_month_june():
    sf = extract_strike_fields("Will Apple reach $250 by end of June 2025?")
    assert sf["price_expiry_month"] == "2025-06"


def test_strike_price_with_commas():
    sf = extract_strike_fields("Will Apple hit $1,500 by end of December 2025?")
    assert sf["strike_price"] == 1500.0


def test_strike_price_decimal():
    sf = extract_strike_fields("Will AAPL close above $182.50 by end of April 2025?")
    assert sf["strike_price"] == 182.50


def test_expiry_year_fallback_from_end_at():
    # Question has month name but no year — fallback to end_at
    end_at = datetime(2025, 3, 31, tzinfo=timezone.utc)
    sf = extract_strike_fields(
        "Will Tesla close above $300 by end of March?",
        end_at=end_at,
    )
    assert sf["price_expiry_month"] == "2025-03"


def test_expiry_year_fallback_from_end_at_iso_string():
    sf = extract_strike_fields(
        "Will Tesla close above $300 by end of March?",
        end_at="2025-03-31T00:00:00Z",
    )
    assert sf["price_expiry_month"] == "2025-03"


def test_expiry_month_fallback_from_end_at_when_no_month_in_text():
    # No month name at all in question — fall back entirely to end_at
    end_at = datetime(2025, 7, 31, tzinfo=timezone.utc)
    sf = extract_strike_fields(
        "Will NVDA close above $600 before expiry?",
        end_at=end_at,
    )
    assert sf["price_expiry_month"] == "2025-07"


def test_no_strike_returns_none():
    sf = extract_strike_fields("Will Apple beat earnings this quarter?")
    assert sf["strike_price"] is None
    assert sf["strike_direction"] is None


def test_all_fields_none_when_no_info():
    sf = extract_strike_fields("Will Apple remain popular?")
    assert sf["strike_price"] is None
    assert sf["strike_direction"] is None
    assert sf["price_expiry_month"] is None


def test_smoke_assertion_from_spec():
    """Exact assertion block from the task specification."""
    sf = extract_strike_fields("Will NVDA close above $500 by end of January 2025?")
    assert sf["strike_price"] == 500.0
    assert sf["strike_direction"] == "above"
    assert sf["price_expiry_month"] == "2025-01", sf


# ─────────────────────────────────────────────────────────────────────────────
# extract_strike_fields — magnitude suffix parsing ($B / $T / $M / $K)
# ─────────────────────────────────────────────────────────────────────────────

def test_strike_price_250b():
    sf = extract_strike_fields("valuation hit $250B by June 2026")
    assert sf["strike_price"] == 250e9, sf


def test_strike_price_4t():
    sf = extract_strike_fields("above $4T by Aug 2026")
    assert sf["strike_price"] == 4e12, sf


def test_strike_price_26_4b():
    sf = extract_strike_fields("gross bookings above $26.4B")
    assert sf["strike_price"] == 26.4e9, sf


def test_strike_price_80b():
    sf = extract_strike_fields("revenue above $80B in FY26")
    assert sf["strike_price"] == 80e9, sf


def test_strike_price_900m():
    sf = extract_strike_fields("revenue exceed $900M in Q2")
    assert sf["strike_price"] == 900e6, sf


def test_strike_price_50k():
    sf = extract_strike_fields("ARR hit $50K by year end")
    assert sf["strike_price"] == 50e3, sf


def test_strike_direction_hit_is_above():
    sf = extract_strike_fields("valuation hit $250B by June 2026")
    assert sf["strike_direction"] == "above"


def test_strike_direction_exceed_is_above():
    sf = extract_strike_fields("market cap exceed $4T by Aug 2026")
    assert sf["strike_direction"] == "above"


def test_strike_direction_reach_is_above():
    sf = extract_strike_fields("revenue reach $80B in FY26")
    assert sf["strike_direction"] == "above"


# ─────────────────────────────────────────────────────────────────────────────
# classify_company_contract — "hit (HIGH/LOW) $X" → price_ladder/price
# ─────────────────────────────────────────────────────────────────────────────

def test_price_ladder_hit_high():
    """Dominant Polymarket phrasing: 'hit (HIGH) $X' → price_ladder/price."""
    result = classify_company_contract(
        {"question": "Will NVDA hit (HIGH) $168 in August 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"
    assert result["company_name"] == "Nvidia"


def test_price_ladder_hit_low():
    """'hit (LOW) $X' → price_ladder/price."""
    result = classify_company_contract(
        {"question": "Will NVDA hit (LOW) $90 in August 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"
    assert result["company_name"] == "Nvidia"


def test_price_ladder_hit_high_direction_above():
    """'hit (HIGH) $X' → strike_direction == 'above'."""
    sf = extract_strike_fields("Will NVDA hit (HIGH) $168 in August 2026?")
    assert sf["strike_price"] == 168.0
    assert sf["strike_direction"] == "above"


def test_price_ladder_hit_low_direction_below():
    """'hit (LOW) $X' → strike_direction == 'below' (not 'above' via bare 'hit')."""
    sf = extract_strike_fields("Will NVDA hit (LOW) $90 in August 2026?")
    assert sf["strike_price"] == 90.0
    assert sf["strike_direction"] == "below"


def test_price_ladder_hit_no_tag():
    """Bare 'hit $X' with no tag → price_ladder/price."""
    result = classify_company_contract(
        {"question": "Will NVDA hit $168 in August 2026?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"


def test_price_ladder_hit_high_apple_parenthetical():
    """Polymarket format 'Apple (AAPL) hit (HIGH) $344' → price_ladder."""
    result = classify_company_contract(
        {"question": "Will Apple (AAPL) hit (HIGH) $344 in July?"}
    )
    assert result is not None
    assert result["contract_family"] == "price_ladder"
    assert result["ladder_metric"] == "price"
    assert result["company_name"] == "Apple"


# ─────────────────────────────────────────────────────────────────────────────
# other_ladder / non-$ thresholds — remain None (no company ladder)
# ─────────────────────────────────────────────────────────────────────────────

def test_non_dollar_threshold_no_company_rejected():
    """'reach 100M users' without a known company → no ladder, rejected."""
    result = classify_company_contract(
        {"question": "Will X reach 100M users?"}
    )
    # "X" is not in COMPANY_DICT, and no $ threshold → None
    assert result is None
