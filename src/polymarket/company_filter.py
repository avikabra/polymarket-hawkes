"""
company_filter.py — Classifier for Polymarket company-contract discovery.

Six INCLUDE families:
  - price_ladder:      share-price strike with a numeric $ threshold
  - market_cap_ladder: market-cap threshold ("market cap exceed $4T")
  - valuation_ladder:  valuation threshold ("valuation hit $250B")
  - revenue_ladder:    revenue / sales / bookings / ARR threshold
  - other_ladder:      any other numeric $ threshold on a company metric
  - corporate_event:   single-company M&A, earnings, CEO/exec, IPO (no threshold)

EXCLUDE checks are applied first (fail-fast), then INCLUDE.
"""

from __future__ import annotations

import re
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Company dictionary — canonical name → list of aliases (names + tickers)
# Promoted verbatim from scratch/enumerate_catalog.py:32-128
# ─────────────────────────────────────────────────────────────────────────────
COMPANY_DICT: dict[str, list[str]] = {
    "Apple": ["Apple", "AAPL"],
    "Microsoft": ["Microsoft", "MSFT"],
    "Google": ["Google", "Alphabet", "GOOGL", "GOOG"],
    "Amazon": ["Amazon", "AMZN"],
    "Meta": ["Meta", "Facebook", "META"],
    "Tesla": ["Tesla", "TSLA"],
    "Nvidia": ["Nvidia", "NVDA", "NVIDIA"],
    "Netflix": ["Netflix", "NFLX"],
    "AMD": ["AMD", "Advanced Micro Devices"],
    "Intel": ["Intel", "INTC"],
    "Qualcomm": ["Qualcomm", "QCOM"],
    "Broadcom": ["Broadcom", "AVGO"],
    "TSMC": ["TSMC", "Taiwan Semiconductor"],
    "ARM": ["ARM", "Arm Holdings"],
    "Micron": ["Micron", "MU"],
    "JPMorgan": ["JPMorgan", "JP Morgan", "JPM"],
    "Goldman Sachs": ["Goldman Sachs"],
    "Morgan Stanley": ["Morgan Stanley"],
    "Bank of America": ["Bank of America", "BAC"],
    "Citigroup": ["Citigroup", "Citi"],
    "Wells Fargo": ["Wells Fargo", "WFC"],
    "Visa": ["Visa"],
    "Mastercard": ["Mastercard"],
    "American Express": ["American Express", "Amex", "AXP"],
    "PayPal": ["PayPal", "PYPL"],
    "BlackRock": ["BlackRock", "BLK"],
    "Pfizer": ["Pfizer", "PFE"],
    "Moderna": ["Moderna", "MRNA"],
    "Merck": ["Merck", "MRK"],
    "Eli Lilly": ["Eli Lilly", "Lilly", "LLY"],
    "AbbVie": ["AbbVie", "ABBV"],
    "UnitedHealth": ["UnitedHealth", "UNH"],
    "Walmart": ["Walmart", "WMT"],
    "Disney": ["Disney", "DIS"],
    "Coca-Cola": ["Coca-Cola", "Coke", "KO"],
    "Nike": ["Nike", "NKE"],
    "McDonald's": ["McDonald's", "McDonalds", "MCD"],
    "Starbucks": ["Starbucks", "SBUX"],
    "Home Depot": ["Home Depot"],
    "Costco": ["Costco", "COST"],
    "ExxonMobil": ["ExxonMobil", "Exxon", "XOM"],
    "Chevron": ["Chevron", "CVX"],
    "Shell": ["Shell", "SHEL"],
    "Boeing": ["Boeing"],
    "Lockheed": ["Lockheed", "LMT"],
    "Ford": ["Ford"],
    "GM": ["General Motors"],
    "Rivian": ["Rivian", "RIVN"],
    "Lucid": ["Lucid Motors", "LCID"],
    "Salesforce": ["Salesforce", "CRM"],
    "Oracle": ["Oracle", "ORCL"],
    "Adobe": ["Adobe", "ADBE"],
    "Palantir": ["Palantir", "PLTR"],
    "Snowflake": ["Snowflake", "SNOW"],
    "Cloudflare": ["Cloudflare", "NET"],
    "Datadog": ["Datadog", "DDOG"],
    "CrowdStrike": ["CrowdStrike", "Crowdstrike", "CRWD"],
    "Palo Alto Networks": ["Palo Alto Networks", "Palo Alto", "PANW"],
    "Shopify": ["Shopify", "SHOP"],
    "Zoom": ["Zoom", "ZM"],
    "Uber": ["Uber", "UBER"],
    "Lyft": ["Lyft", "LYFT"],
    "Airbnb": ["Airbnb", "ABNB"],
    "DoorDash": ["DoorDash", "DASH"],
    "Roblox": ["Roblox", "RBLX"],
    "Coinbase": ["Coinbase", "COIN"],
    "Robinhood": ["Robinhood Markets", "HOOD"],
    "Block": ["Block Inc", "Square"],
    "MicroStrategy": ["MicroStrategy", "MSTR"],
    "GameStop": ["GameStop", "GME"],
    "AMC": ["AMC Entertainment"],
    "Reddit": ["Reddit", "RDDT"],
    "Instacart": ["Instacart", "CART"],
    "AT&T": ["AT&T"],
    "Verizon": ["Verizon", "VZ"],
    "T-Mobile": ["T-Mobile", "TMUS"],
    "Comcast": ["Comcast", "CMCSA"],
    "Warner Bros": ["Warner Bros", "WBD"],
    "OpenAI": ["OpenAI"],
    "SpaceX": ["SpaceX", "Starlink"],
    "Stripe": ["Stripe"],
    "Anthropic": ["Anthropic"],
    "Databricks": ["Databricks"],
    "Klarna": ["Klarna"],
    "Waymo": ["Waymo"],
    "xAI": ["xAI"],
    "IBM": ["IBM"],
    "ServiceNow": ["ServiceNow", "NOW"],
    "Intuit": ["Intuit", "INTU"],
    "Workday": ["Workday", "WDAY"],
    "Fortinet": ["Fortinet", "FTNT"],
    "Super Micro": ["Super Micro", "SMCI"],
    "Dell": ["Dell", "DELL"],
    "HP": ["HP Inc", "Hewlett"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Build flat alias → canonical mapping + compiled regex
# Verbatim from scratch/enumerate_catalog.py:131-143
# ─────────────────────────────────────────────────────────────────────────────
_NAME_TO_CANON: dict[str, str] = {}
_TICKER_TO_CANON: dict[str, str] = {}  # ticker string (e.g. "NVDA") → canonical
_ALL_ALIASES: list[str] = []

for _canon, _aliases in COMPANY_DICT.items():
    for _alias in _aliases:
        _NAME_TO_CANON[_alias.lower()] = _canon
        _ALL_ALIASES.append(_alias)
        # Track tickers (2-5 uppercase letters that are all caps in the alias list)
        if _alias.isupper() and 2 <= len(_alias) <= 5:
            _TICKER_TO_CANON[_alias] = _canon

_ALL_ALIASES.sort(key=len, reverse=True)  # longest-first avoids partial shadowing

# ─────────────────────────────────────────────────────────────────────────────
# GDELT entity-regex helpers (Weeks 7-9) — shared by scripts/04_pull_gdelt_corpus.py
# and scripts/audit_gdelt_company_coverage.py. Promoted verbatim from the audit
# script (pure refactor; behavior unchanged) so both stay in lockstep.
# ─────────────────────────────────────────────────────────────────────────────

# Aliases that are ordinary English words or shadow unrelated organisations.
# Kept in the universe classifier above (where the question text disambiguates)
# but excluded from the GDELT entity regex, where they would swamp the counts.
AMBIGUOUS_GDELT_ALIASES = {
    "ARM", "Block", "Block Inc", "Square", "Shell", "Visa", "Intel",
    "Lucid", "AMC", "Coke", "Citi", "Amex",
}


def gdelt_entity_aliases(canon: str, aliases: list[str]) -> list[str]:
    """Name-like aliases only: drop bare tickers and ambiguous common words."""
    out = [
        a for a in aliases
        if not (a.isupper() and 2 <= len(a) <= 5) and a not in AMBIGUOUS_GDELT_ALIASES
    ]
    return out or ([canon] if canon not in AMBIGUOUS_GDELT_ALIASES else [])


def build_gdelt_entity_patterns(company_dict: dict[str, list[str]] | None = None) -> dict[str, str]:
    """Per-company `(?i)(alias1|alias2|...)` regex patterns for GDELT entity fields."""
    company_dict = COMPANY_DICT if company_dict is None else company_dict
    pats: dict[str, str] = {}
    for canon, aliases in company_dict.items():
        names = gdelt_entity_aliases(canon, aliases)
        if not names:
            continue
        alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        pats[canon] = f"(?i)({alt})"
    return pats

COMPANY_NAME_PAT = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _ALL_ALIASES) + r")\b",
    re.IGNORECASE,
)
TICKER_PAT = re.compile(r"\$([A-Z]{2,5})\b")

# ─────────────────────────────────────────────────────────────────────────────
# Classification regexes — verbatim from scratch/enumerate_catalog.py:149-192
# ─────────────────────────────────────────────────────────────────────────────

CORPORATE_SIGNALS = re.compile(
    r"\b(?:stock|share(?:s)?|ticker|earnings|EPS|revenue|profit|quarterly|fiscal|"
    r"guidance|valuation|market\s?cap|IPO|acquisition|merger|M&A|buyout|spinoff|"
    r"dividend|close\s+above|close\s+below|closes?\s+at|price|target|"
    r"hit(?:s)?\s+\$|reach(?:es)?\s+\$|all.time\s+high|ATH|"
    r"split|buyback|CEO|CTO|CFO|COO|executive|board|layoff|"
    r"listed|S-1|10-K|10-Q|annual|quarterly\s+results|"
    r"above\s+\$|below\s+\$|exceed|beat|miss|surpass|"
    r"market\s+cap|go\s+public|direct\s+listing)\b",
    re.IGNORECASE,
)

SPORTS_PAT = re.compile(
    r"\b(?:win(?:s)?|defeat|beat|score|game|match|series|playoff|"
    r"championship|Super Bowl|NBA|NFL|MLB|NHL|UFC|FIFA|World Cup|Olympics|"
    r"touchdown|goal|bracket|tournament|tennis|golf|Formula\s*1|F1|Grand Prix|"
    r"boxing|wrestling|esport|League of Legends|LCS|LEC|BLAST)\b",
    re.IGNORECASE,
)

POLITICS_PAT = re.compile(
    r"\b(?:election|vote|ballot|president|senator|congress|Republican|Democrat|"
    r"White House|governor|mayor|poll|approval\s+rating|Supreme Court|"
    r"will\s+(?:he|she|they)\s+(?:say|mention|tweet)|"
    r"Fed(?:eral\s+Reserve)?|FOMC|interest\s+rate|Federal\s+funds|"
    r"tariff|sanction|geopoliti|NATO|war|invasion)\b",
    re.IGNORECASE,
)

PURE_CRYPTO_PAT = re.compile(
    r"\b(?:Bitcoin|BTC|Ethereum|ETH|Solana|SOL|Dogecoin|DOGE|XRP|Ripple|"
    r"Cardano|ADA|Polkadot|DOT|Avalanche|AVAX|Chainlink|LINK|Litecoin|LTC|"
    r"Shiba|SHIB|BONK|PEPE|meme\s*coin|NFT|DeFi|Web3|crypto\s*currency|"
    r"altcoin|staking|mining|hash\s*rate|gas\s*fee|mempool|dao|"
    r"yield\s*farm|liquidity\s*pool|Tether|USDT|USDC|stablecoin)\b",
    re.IGNORECASE,
)

DAILY_SERIES_PAT = re.compile(
    r"\b(?:close\s+above|close\s+below|closes?\s+(?:above|below|at|over|under)|"
    r"end\s+(?:above|below|at)|all.time\s+high|ATH|hit(?:s)?\s+\$|reach(?:es)?\s+\$|"
    r"above\s+\$\d|below\s+\$\d|touch\s+\$|break(?:s)?\s+\$)\b",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# New exclude regexes (custom, per spec §B.3)
# ─────────────────────────────────────────────────────────────────────────────

# MicroStrategy/MSTR + Bitcoin/BTC in the same question (BTC-treasury series).
# MSTR earnings/CEO questions (no BTC mention) should pass through.
_MSTR_BTC_PAT = re.compile(
    r"\b(?:MicroStrategy|MSTR)\b.{0,200}\b(?:Bitcoin|BTC)\b"
    r"|"
    r"\b(?:Bitcoin|BTC)\b.{0,200}\b(?:MicroStrategy|MSTR)\b",
    re.IGNORECASE | re.DOTALL,
)

# AI-model-leadership markets: "best AI model", "top AI", "beat Claude/GPT/Gemini" etc.
_AI_LEADERSHIP_PAT = re.compile(
    r"\b(?:"
    r"best\s+(?:AI|LLM|language)\s+model"
    r"|top\s+AI\s+(?:model|lab|company)"
    r"|leading\s+AI\s+(?:model|lab)"
    r"|most\s+capable\s+model"
    r"|frontier\s+model"
    r"|best\s+LLM"
    r"|outperform\s+(?:GPT|Claude|Gemini|Llama|Grok)"
    r"|beat\s+(?:GPT|Claude|Gemini|Llama|Grok)"
    r"|better\s+than\s+(?:GPT|Claude|Gemini|Llama|Grok)"
    r"|model.{0,20}(?:ranking|leaderboard|benchmark|competition)"
    r")\b",
    re.IGNORECASE,
)

# Commodity / index price markets (without a named company context).
_COMMODITY_INDEX_PAT = re.compile(
    r"\b(?:"
    r"gold|silver|oil|crude|WTI|Brent|natural\s+gas|wheat|corn|copper|platinum"
    r"|S&P\s*500|S&P500|SPX|SPY"
    r"|Nasdaq\s*100|NDX|QQQ"
    r"|Dow\s+Jones|DJIA|DJI"
    r"|Russell\s+(?:1000|2000|3000)"
    r"|VIX|CBOE\s+Volatility"
    r")\b",
    re.IGNORECASE,
)

# "Will [person/entity] say/mention/tweet/post [something]" speech markets.
_SPEECH_MARKET_PAT = re.compile(
    r"\bwill\s+\w+(?:\s+\w+){0,3}\s+(?:say|mention|tweet|post|announce)\b",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Dollar amount pattern — supports magnitude suffixes B/T/M/K and commas.
# Group 1: numeric part (with optional commas/decimal)
# Group 2: optional suffix letter (B/T/M/K, case-insensitive)
# ─────────────────────────────────────────────────────────────────────────────
_DOLLAR_STRIKE_PAT = re.compile(
    r"\$(\d[\d,]*(?:\.\d+)?)([BMKTbmkt])?\b"
)

_SUFFIX_MULTIPLIERS: dict[str, float] = {
    "b": 1e9,
    "t": 1e12,
    "m": 1e6,
    "k": 1e3,
}

# Strike direction verbs — extended to include hit/reach for ladder thresholds.
# "beat" and "surpass" are omitted because they match sports/earnings language.
_ABOVE_PAT = re.compile(r"\b(?:above|over|exceed|hit(?:s)?|reach(?:es)?)\b", re.IGNORECASE)
_BELOW_PAT = re.compile(r"\b(?:below|under)\b", re.IGNORECASE)

# Explicit parenthetical direction tags used by Polymarket: "hit (HIGH)" / "hit (LOW)"
# Checked first in direction resolution so "(LOW)" overrides the bare "hit" → above reading.
_HIT_HIGH_PAT = re.compile(r"\bhit\s*\(\s*HIGH\s*\)", re.IGNORECASE)
_HIT_LOW_PAT = re.compile(r"\bhit\s*\(\s*LOW\s*\)", re.IGNORECASE)

# Month name → month number
_MONTH_MAP: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Match "January 2025" or "end of January 2025" or just "January" / "end of January"
_MONTH_YEAR_PAT = re.compile(
    r"\b(?:end\s+of\s+)?("
    + "|".join(_MONTH_MAP.keys())
    + r")\b(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

# Corporate-event keywords for Family B (subset of CORPORATE_SIGNALS, more specific)
_CORP_EVENT_PAT = re.compile(
    r"\b(?:"
    r"acquisition|acqui(?:re|red|ring)|merger|M&A|buyout|takeover|go\s+private|spinoff"
    r"|earnings|EPS|quarterly\s+results|annual\s+results|guidance|fiscal"
    r"|CEO|CFO|CTO|COO|resign|fire(?:d)?|hire(?:d)?|appoint(?:ed)?|executive|layoff"
    r"|IPO|go\s+public|direct\s+listing|S-1"
    r")\b",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Metric-detection patterns (checked in priority order)
# Each pattern identifies a SPECIFIC metric keyword near a $ threshold.
# ─────────────────────────────────────────────────────────────────────────────

# market_cap: "market cap" / "market capitalization" + numeric $ threshold
# "largest company by market cap" with NO $ threshold is NOT a ladder.
_MARKET_CAP_PAT = re.compile(
    r"\bmarket\s+cap(?:italization)?\b",
    re.IGNORECASE,
)

# valuation: "valuation" / "valued at" / "worth $XB" / IPO valuation context
_VALUATION_PAT = re.compile(
    r"\b(?:valuation|valued?\s+at|worth\s+\$)\b",
    re.IGNORECASE,
)

# revenue: "revenue" / "sales" / "gross booking(s)" / "bookings" / "ARR"
_REVENUE_PAT = re.compile(
    r"\b(?:revenue|sales|gross\s+booking(?:s)?|booking(?:s)?\s+value|ARR|"
    r"gross\s+merchandise\s+value|GMV)\b",
    re.IGNORECASE,
)

# price: share-price / stock-price signals
# "close above/below $X", "stock above/below $X", "share price ... $X"
_PRICE_METRIC_PAT = re.compile(
    r"\b(?:close\s+(?:above|below|over|under)|stock\s+(?:above|below|over|under)|"
    r"share\s+price|stock\s+price|price\s+(?:above|below|over|under)|"
    r"closes?\s+(?:above|below)|stock\s+hit|share\s+hit)\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_dollar_amount(text: str) -> float | None:
    """Parse the first '$<number>[suffix]' in text, applying B/T/M/K multipliers."""
    m = _DOLLAR_STRIKE_PAT.search(text)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = (m.group(2) or "").lower()
    multiplier = _SUFFIX_MULTIPLIERS.get(suffix, 1.0)
    return value * multiplier


def _resolve_company(question: str) -> tuple[str, str | None] | None:
    """Return (canonical_name, ticker_or_None) for the first company found, or None."""
    # Try $TICKER first
    m = TICKER_PAT.search(question)
    if m:
        ticker = m.group(1).upper()
        canon = _TICKER_TO_CANON.get(ticker)
        if canon:
            return canon, ticker
    # Try name match
    m = COMPANY_NAME_PAT.search(question)
    if m:
        alias = m.group(1)
        canon = _NAME_TO_CANON.get(alias.lower(), alias)
        # Look up a ticker for this canonical name
        aliases = COMPANY_DICT.get(canon, [])
        ticker = next(
            (a for a in aliases if a.isupper() and 2 <= len(a) <= 5),
            None,
        )
        return canon, ticker
    return None


def _has_numeric_threshold(question: str) -> bool:
    """True if question contains a '$<number>[suffix]' with a direction verb."""
    if not _DOLLAR_STRIKE_PAT.search(question):
        return False
    return bool(_ABOVE_PAT.search(question) or _BELOW_PAT.search(question))


def _has_dollar_amount(question: str) -> bool:
    """True if question contains any '$<number>[suffix]' amount."""
    return bool(_DOLLAR_STRIKE_PAT.search(question))


def _detect_ladder_metric(question: str) -> tuple[str, str] | None:
    """
    Detect which ladder metric applies.

    Returns (contract_family, ladder_metric) or None if no ladder detected.

    Priority: market_cap > valuation > revenue > price_ladder (default).

    Named-metric keywords (market_cap / valuation / revenue) are checked first
    so they always win when their keyword is present.  Any remaining
    $-denominated threshold with a direction verb (including bare "hit (HIGH)
    $168" phrasing) falls through to price_ladder/price — the dominant
    Polymarket share-price ladder form.

    For market_cap / price: requires a direction verb alongside the $ threshold.
    For valuation / revenue: a $ threshold alone is sufficient because the
    metric keyword already encodes the target level.
    """
    has_dollar = _has_dollar_amount(question)
    if not has_dollar:
        return None

    has_direction = bool(
        _ABOVE_PAT.search(question)
        or _BELOW_PAT.search(question)
        or _HIT_HIGH_PAT.search(question)
        or _HIT_LOW_PAT.search(question)
    )

    # Market cap ladder: direction verb required (avoids "largest by market cap")
    if has_direction and _MARKET_CAP_PAT.search(question):
        return ("market_cap_ladder", "market_cap")

    # Valuation ladder: "valued at $X" / "valuation hit $X" — direction optional.
    if _VALUATION_PAT.search(question):
        return ("valuation_ladder", "valuation")

    # Revenue ladder: metric keyword + dollar amount — direction optional.
    if _REVENUE_PAT.search(question):
        return ("revenue_ladder", "revenue")

    # Price ladder (default for bare $-denominated thresholds with direction verb).
    # Covers "close above/below $X", "hit (HIGH/LOW) $X", "hit $X", "reach $X",
    # "above $X", "below $X", "over $X", "under $X", etc.
    # Explicit price-metric keywords (_PRICE_METRIC_PAT) also land here.
    if has_direction:
        return ("price_ladder", "price")

    return None


def _is_price_ladder(question: str) -> bool:
    """True if the question is a share-price threshold ladder (legacy helper)."""
    # Either an explicit price-metric keyword, or the plain numeric + direction pattern
    # that DAILY_SERIES_PAT catches (e.g. "reach $190 end of July").
    if not _has_numeric_threshold(question):
        # Check DAILY_SERIES_PAT even when _ABOVE_PAT/_BELOW_PAT miss (edge case)
        return bool(DAILY_SERIES_PAT.search(question) and _DOLLAR_STRIKE_PAT.search(question))
    return True


def _is_corporate_event(question: str) -> bool:
    """True if the question contains corporate-event keywords."""
    return bool(_CORP_EVENT_PAT.search(question))


def _is_excluded(question: str) -> bool:
    """Return True if the question matches any hard-exclude rule."""
    # Sports — but allow through if a corporate-event signal is also present
    # (e.g. "beat earnings" should not be excluded by the bare word "beat").
    if SPORTS_PAT.search(question) and not _CORP_EVENT_PAT.search(question):
        return True
    # Politics / macro
    if POLITICS_PAT.search(question):
        return True
    # MicroStrategy + BTC treasury series (must check before pure-crypto test
    # so that "MSTR earnings" without BTC is not caught here)
    if _MSTR_BTC_PAT.search(question):
        return True
    # Pure crypto (no company name present)
    if PURE_CRYPTO_PAT.search(question) and not COMPANY_NAME_PAT.search(question):
        return True
    # AI model leadership
    if _AI_LEADERSHIP_PAT.search(question):
        return True
    # Commodity / index price (no company name present)
    if _COMMODITY_INDEX_PAT.search(question) and not COMPANY_NAME_PAT.search(question):
        return True
    # Speech markets
    if _SPEECH_MARKET_PAT.search(question):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def classify_company_contract(raw: dict) -> dict | None:
    """Classify a raw Gamma market dict.

    Returns a classification dict on acceptance, None on rejection.

    Classification dict keys:
        contract_family: "price_ladder" | "market_cap_ladder" | "valuation_ladder" |
                         "revenue_ladder" | "other_ladder" | "corporate_event"
        ladder_metric:   "price" | "market_cap" | "valuation" | "revenue" | "other" | None
        company_name:    canonical name from COMPANY_DICT
        ticker:          str | None (None for private companies)
        company_id:      stable slug (lowercased canonical, spaces → underscores)
    """
    question = raw.get("question", "")

    # Step 1: apply all exclude checks first
    if _is_excluded(question):
        return None

    # Step 2: resolve a company; if none found, reject
    resolved = _resolve_company(question)
    if resolved is None:
        return None
    company_name, ticker = resolved

    # Step 3: determine contract family — ladder detection takes priority
    ladder = _detect_ladder_metric(question)
    if ladder is not None:
        family, metric = ladder
    elif _is_corporate_event(question):
        family, metric = "corporate_event", None
    else:
        return None

    company_id = company_name.lower().replace(" ", "_")
    return {
        "contract_family": family,
        "ladder_metric": metric,
        "company_name": company_name,
        "ticker": ticker,
        "company_id": company_id,
    }


def extract_strike_fields(
    question: str,
    end_at: datetime | str | None = None,
) -> dict:
    """Extract structured fields from a ladder-type question.

    Returns:
        strike_price:        float | None    e.g. 500.0, 250e9, 4e12
        strike_direction:    "above"|"below"|None
        price_expiry_month:  str | None      e.g. "2025-01" (ISO YYYY-MM)

    Dollar amounts support magnitude suffixes: B (billion), T (trillion),
    M (million), K (thousand).  E.g. "$250B" → 250e9, "$4T" → 4e12.

    If year is absent from the question text, it is derived from `end_at`
    (a datetime or ISO string).  Month is similarly derived from `end_at`
    if no month name appears in the question.
    """
    # Parse end_at into a datetime for fallback
    end_dt: datetime | None = None
    if isinstance(end_at, datetime):
        end_dt = end_at
    elif isinstance(end_at, str):
        try:
            end_dt = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
        except ValueError:
            end_dt = None

    # strike_price (with magnitude suffix support)
    strike_price: float | None = _parse_dollar_amount(question)

    # strike_direction — explicit parenthetical tags take precedence over bare verbs
    # so "hit (LOW) $90" correctly resolves to "below" rather than "above" (via "hit").
    strike_direction: str | None = None
    if _HIT_HIGH_PAT.search(question):
        strike_direction = "above"
    elif _HIT_LOW_PAT.search(question):
        strike_direction = "below"
    elif _ABOVE_PAT.search(question):
        strike_direction = "above"
    elif _BELOW_PAT.search(question):
        strike_direction = "below"

    # price_expiry_month
    price_expiry_month: str | None = None
    m = _MONTH_YEAR_PAT.search(question)
    if m:
        month_name = m.group(1).lower()
        month_num = _MONTH_MAP.get(month_name)
        year_str = m.group(2)
        if month_num is not None:
            if year_str:
                year = int(year_str)
            elif end_dt is not None:
                year = end_dt.year
            else:
                year = datetime.utcnow().year
            price_expiry_month = f"{year:04d}-{month_num:02d}"
    elif end_dt is not None:
        # No month name in question — fall back to end_at month entirely
        price_expiry_month = end_dt.strftime("%Y-%m")

    return {
        "strike_price": strike_price,
        "strike_direction": strike_direction,
        "price_expiry_month": price_expiry_month,
    }
