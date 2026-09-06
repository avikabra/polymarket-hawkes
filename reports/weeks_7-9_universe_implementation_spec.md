# Weeks 7-9: Universe Discovery — Implementation Spec

**Status:** Implementation-ready plan. No pipeline code was modified to produce this document.
**Repo root:** `/Users/home/Desktop/MAIN/Coding/thesis-polymarket`
**Date authored:** 2026-08-29
**Supersedes:** the category-loop approach in `scripts/01_discover_universe.py`; decisions from `reports/weeks_7-9_direction.md §4.1`

---

## A. Productionize Day-Sliced Enumeration in `GammaClient`

### Why this method

The `/markets` endpoint has a hard **offset ceiling of ≈2,100 items per query** regardless of filter combination (`closed`, `tag_id`, unfiltered). The `/events?tag_id` route used in the current `list_markets` (gamma.py:95–143) hits the same ceiling and additionally requires tag-slug → numeric-ID resolution (gamma.py:87–93), which silently returns zero results if the slug is not found.

`scratch/enumerate_catalog.py` discovered the correct strategy: **day-level slicing on `/markets` with `end_date_min` / `end_date_max` clamped to a 24-hour window** (enumerate_catalog.py:384–413). Each calendar day stays well under 2,100 markets, so the ceiling is never reached. For each day two passes are run — `closed=true` and `closed=false` — then deduplicated on `conditionId` (enumerate_catalog.py:393–412).

### New method: `GammaClient.enumerate_markets(start, end)`

Add to `src/polymarket/gamma.py` alongside the existing `list_markets` and `get_market` methods. The existing `list_markets` must NOT be deleted yet — script 05 (news-fetch) reads `categories.yaml` tags and may still use it.

**Signature (illustrative — spec only, do not copy into pipeline files):**
```python
async def enumerate_markets(
    self,
    start: datetime,   # UTC; inclusive lower bound on endDate
    end: datetime,     # UTC; exclusive upper bound on endDate
    *,
    page_limit: int = 100,
    inter_page_sleep: float = 0.25,   # conservative; scratch used 0.08
    inter_day_sleep: float = 1.0,     # additional pause between days
) -> AsyncIterator[dict]:
    """Yield raw market dicts for all markets whose endDate falls in [start, end).

    Uses day-level slicing to stay under the ~2,100-offset ceiling.
    Results are deduplicated within a day by conditionId; cross-day
    deduplication is the caller's responsibility (use a seen-set on conditionId).
    Yields markets, does not accumulate them — caller controls memory.
    """
```

**Pagination loop (per day, per closed-value) — must match enumerate_catalog.py:393–412:**
- Params: `limit=page_limit`, `offset` incremented by `page_limit`, `end_date_min=ds`, `end_date_max=de`, `closed=val`.
- Stop condition: `len(page) < page_limit` (enumerate_catalog.py:408).
- 422 → treat as end-of-results, not an error (enumerate_catalog.py:366).
- 429 → back off and retry (enumerate_catalog.py:368–370); the existing `TokenBucket` in `GammaClient.__init__` (gamma.py:63) can pace inter-page requests; supplement with the explicit `inter_page_sleep`.
- Network errors → retry up to 3× with exponential back-off; log and continue to next day on repeated failure.

**Resumability:** Cache is already implemented via `DiskCache` (src/utils/cache.py:1–22). The cache key for each page call should be `f"/markets?end_date_min={ds}&end_date_max={de}&closed={val}&offset={offset}"` — same scheme as the existing `_get` method (gamma.py:73). On re-run, cached pages are served from disk; days not yet fetched are pulled fresh. This makes an interrupted run resumable at the page granularity.

**Rate-limiting target:** `inter_page_sleep=0.25s` (3× conservative vs. the 0.08s scratch value, enumerate_catalog.py:356). Full 2024-01-01 → present enumeration at 1 req/0.25s across ≈750 days × ≈5 pages/day × 2 closed-values ≈ 7,500 requests ≈ 30 minutes cold; subsequent runs hit cache and are fast.

**Active/future supplement:** After the day-slice loop finishes, run a supplemental pass querying `active=true&closed=false` with offset looping (capped at 2,100 to respect the ceiling — enumerate_catalog.py:462–468). Merge new conditionIds into the seen-set. This catches markets whose `endDate` is in the future and would otherwise be missed by the endDate-bounded slice.

---

## B. New Classifier Module: `src/polymarket/company_filter.py`

This module is the gate that converts a raw Gamma market dict into a classified company contract or rejects it. It does not touch network or storage — pure text logic.

### B.1 Company dictionary

Promote the `COMPANY_DICT` from `scratch/enumerate_catalog.py:32–128` into `company_filter.py` as a module-level constant. Extend with additional private-company names as they are encountered. The dictionary maps canonical company name → list of name/ticker aliases (same structure as scratch:32–128).

Build the flat alias lookup and compiled regex from the dictionary using the same sort-by-length pattern (enumerate_catalog.py:131–143) to prevent partial-name shadowing. `TICKER_PAT = re.compile(r"\$([A-Z]{2,5})\b")` (enumerate_catalog.py:143) is also kept.

### B.2 INCLUDE logic — two contract families

**Family A: Monthly stock-price strike contracts**

Signals (all must match):
1. Company name or ticker present in the question text (via `COMPANY_NAME_PAT` or `TICKER_PAT`).
2. Strike price present: regex matching `\$\d+` with a dollar sign and number.
3. Expiry month/date present: month name or "end of [month]" or explicit date pattern.
4. Price-direction verb present: "close above", "close below", "close at", "above \$", "below \$", "exceed \$", "reach \$", "hit \$", "end above", "end below" (draw from `DAILY_SERIES_PAT` in enumerate_catalog.py:187–193 and `CORPORATE_SIGNALS` in enumerate_catalog.py:149–158).

The question must NOT contain sport/politics/crypto exclusion signals (see §B.3).

**Family B: One-off corporate-event contracts**

Signals (company present + at least one corporate-event keyword, no exclusion signals):
- M&A keywords: "acquisition", "merger", "acquire", "M&A", "buyout", "takeover", "go private".
- Earnings keywords: "earnings", "EPS", "revenue", "quarterly results", "annual results", "beat", "miss", "guidance", "fiscal".
- CEO/exec keywords: "CEO", "CFO", "CTO", "COO", "resign", "fire", "hire", "appoint", "executive", "board".
- IPO / valuation keywords: "IPO", "go public", "direct listing", "S-1", "valuation", "market cap" (when tied to a private company name or a named company's fundraise).

### B.3 EXCLUDE patterns (applied before INCLUDE check)

Each pattern below triggers rejection regardless of INCLUDE signals. Patterns are applied to the full question text (`question` field). Draw from the scratch regexes (enumerate_catalog.py:149–193) and extend:

| Category | Key patterns | Source |
|---|---|---|
| Sports | NBA, NFL, MLB, NHL, UFC, FIFA, World Cup, Super Bowl, Olympics, championship, playoff, bracket, game, match, F1, Grand Prix | enumerate_catalog.py:162–167 |
| Politics / macro | election, vote, president, Fed, FOMC, interest rate, tariff, sanction, NATO, war, geopoliti | enumerate_catalog.py:169–176 |
| Pure crypto-token price | Bitcoin, BTC, Ethereum, ETH, Solana, SOL, Dogecoin, DOGE, XRP, NFT, DeFi, memecoin, staking, gas fee | enumerate_catalog.py:178–185 |
| MicroStrategy/BTC series | "MicroStrategy" OR "MSTR" when the question also contains "Bitcoin" or "BTC" (MSTR-as-company earnings/CEO questions remain IN) | custom |
| AI-model-leadership | "best AI model", "leading AI", "most capable model", "frontier model", "best LLM", "outperform GPT", "beat Claude", "beat Gemini" | custom |
| Commodity / index price | "oil", "gold", "silver", "S&P 500", "Nasdaq 100", "Dow Jones", "Russell", "crude", "wheat", "corn", "natural gas" (without a named company) | custom |
| Speech markets | "will [name] say", "will [name] mention", "will [name] tweet", "will [name] post" | enumerate_catalog.py:172 partial |

### B.4 Public function: `classify_company_contract`

```python
def classify_company_contract(raw: dict) -> dict | None:
    """Classify a raw Gamma market dict.

    Returns a classification dict on acceptance, None on rejection.
    Classification dict keys:
        company_name: str          canonical name from COMPANY_DICT
        ticker: str | None         e.g. "NVDA"; None for private companies
        contract_family: Literal["monthly_strike", "corporate_event"]
        is_primary_sample: bool    True for both families (replaces old sports logic)
        exclude_reason: None       (None on acceptance)
    Returns None if excluded; call site should log exclude_reason separately.
    """
```

The function checks EXCLUDE patterns first (fail fast), then INCLUDE logic for Family A and Family B in order. If neither family matches → None.

### B.5 Public function: `extract_strike_fields`

Called only for Family A contracts.

```python
def extract_strike_fields(question: str) -> dict:
    """Extract structured fields from a monthly-strike question.

    Returns:
        strike_price: float | None      e.g. 190.0
        strike_direction: Literal["above", "below"] | None
        price_expiry_month: str | None  e.g. "2025-07" (ISO year-month)
    """
```

Use `re.search(r"\$(\d+(?:\.\d+)?)", question)` for `strike_price`. Use "above"/"below" keyword scan for `strike_direction`. For `price_expiry_month`, match month names ("January" … "December") or "end of [month]" then map to ISO `YYYY-MM` using the market's `end_at` date as year context if the question omits the year.

---

## C. Schema Changes — `src/schemas/market.py`

Current schema (market.py:1–27). Every change below is additive or a replacement of the `market_type` Literal; no existing column is removed to preserve 02/03 compatibility.

### C.1 Fields to ADD

```python
# Company identity
company_name: str | None          # canonical name from COMPANY_DICT; None if unmatched
ticker: str | None                # exchange ticker symbol; None for private companies
company_id: str                   # stable slug: company_name.lower().replace(" ", "_")
                                  # used to group corporate-event contracts per company

# Contract family (replaces market_type for the new universe)
contract_family: Literal["monthly_strike", "corporate_event", "other"]

# Strike-ladder fields (populated for monthly_strike; None otherwise)
strike_price: float | None        # e.g. 190.0
strike_direction: Literal["above", "below"] | None
price_expiry_month: str | None    # ISO year-month e.g. "2025-07"

# Parent/child grouping
group_id: str                     # for monthly_strike: f"{company_id}_{price_expiry_month}"
                                  # for corporate_event: market_id (standalone)
group_role: Literal["child", "standalone"]
                                  # "child" for monthly strikes; "standalone" for events
                                  # (no synthetic parent row is emitted — see §C.3)

# Liquidity fields recorded at discovery (no floor applied)
volume_1wk: float                 # Gamma field "volume1wk"; 0.0 if absent
volume_1mo: float                 # Gamma field "volume1mo"; 0.0 if absent
# volumeNum already maps to total_volume_usdc (gamma.py:173); keep that name
```

### C.2 Fields to REPLACE

`market_type` Literal (market.py:21–24) is replaced:

```python
# OLD (market.py:21-24):
market_type: Literal[
    "season_long", "championship", "playoff_series",
    "conference", "single_game", "other"
]

# NEW:
contract_family: Literal["monthly_strike", "corporate_event", "other"]
```

`market_type` is removed from the schema entirely. `contract_family` is the replacement discriminator.

### C.3 `is_primary_sample` redefined

```python
# OLD (market.py:26-27, gamma.py:191-192): sport-market-type membership test
is_primary_sample: bool   # was: market_type in _PRIMARY_TYPES

# NEW: classifier-accepted contracts
is_primary_sample: bool   # True iff contract_family in ("monthly_strike", "corporate_event")
```

### C.4 Parent rows: sidecar parquet, NOT synthetic rows

**Decision: emit a sidecar `data/polymarket/contract_groups.parquet` rather than inserting synthetic parent rows into `universe.parquet`.**

Rationale: `universe.parquet` is the authoritative list of real on-chain contracts. A synthetic parent row without a `conditionId` would break `02_pull_trades.py` (which iterates `universe.parquet` and fetches Goldsky fills per `yes_token_id` / `no_token_id` — scripts/02:58–94) and `03_resample_trades.py` (which joins on `market_id` — scripts/03:41–43). A sidecar avoids this entirely.

`contract_groups.parquet` schema (one row per group):

| Column | Type | Description |
|---|---|---|
| `group_id` | str | f"{company_id}_{price_expiry_month}" for strikes; market_id for events |
| `company_name` | str | canonical name |
| `ticker` | str or null | exchange ticker |
| `contract_family` | str | "monthly_strike" or "corporate_event" |
| `price_expiry_month` | str or null | ISO year-month for strikes; null for events |
| `member_market_ids` | list[str] | conditionIds of all child/member contracts |
| `strike_prices` | list[float] or null | sorted ascending list for strikes; null for events |
| `total_volume_usdc_sum` | float | sum of volumeNum across members |

`group_id` is written into every row of `universe.parquet` as a regular column. It survives into trades (02) and bars (03) because those scripts carry through all universe columns onto their partition paths; `group_id` is then available for any downstream join.

---

## D. Rewrite `scripts/01_discover_universe.py`

### D.1 What to DELETE

| Item | Current location | Reason for removal |
|---|---|---|
| Category loop over `focal["categories"]` | 01:83–100 | Replaced by date-sliced enumeration |
| `_overlap_fraction` helper | 01:29–36 | Used only by `_link_correlated` |
| `_link_correlated` function | 01:39–55 | Sports-era correlation heuristic; not meaningful for strike ladders |
| `min_volume_usdc` filter | 01:110–111 | Volume floor removed — recorded but not applied at discovery |
| `min_market_duration_days` filter | 01:108–109 | Duration filter removed entirely |
| Read of `categories.yaml` | 01:77 | No longer needed by script 01 |
| `market_types.primary` config read | 01:118 | Replaced by `contract_family` logic |

### D.2 What to ADD

**Discovery loop:**
```
seen_ids: set[str] = {}
async for raw in client.enumerate_markets(start=start_dt, end=end_dt):
    cid = raw.get("conditionId", "")
    if not cid or cid in seen_ids:
        continue
    seen_ids.add(cid)

    result = classify_company_contract(raw)
    if result is None:
        continue

    strike_fields = extract_strike_fields(raw["question"]) \
        if result["contract_family"] == "monthly_strike" else {}

    market = client.parse_market(raw, classification=result, strike_fields=strike_fields)
    markets.append(market)
```

**`parse_market` extended signature:** `gamma.py`'s `parse_market` receives `classification` and `strike_fields` dicts and populates the new schema fields. The old `category` parameter is retired.

**`group_id` assignment:** After the enumeration loop, compute `group_id` and `group_role`:
```
for m in markets:
    if m.contract_family == "monthly_strike":
        m.group_id = f"{m.company_id}_{m.price_expiry_month}"
        m.group_role = "child"
    else:
        m.group_id = m.market_id
        m.group_role = "standalone"
```

**Sidecar generation:** Build `contract_groups.parquet` by grouping accepted markets on `group_id`. Sort `strike_prices` ascending within each group.

**Config read:** Read only `config/focal.yaml` for `start_date` and `end_date`. Do NOT read `categories.yaml` in script 01.

**Output columns for `universe.parquet`:**

All existing columns (market_id, slug, question, description, tags, created_at, end_at, resolved_at, yes_token_id, no_token_id, resolved_outcome, total_volume_usdc, parent_event_id, is_primary_sample) PLUS the new columns from §C.1: company_name, ticker, company_id, contract_family, strike_price, strike_direction, price_expiry_month, group_id, group_role, volume_1wk, volume_1mo.

**Loud-fail guards (update existing, preserve spirit of current 01:123–134):**

```python
# Guard 1 — no markets at all
if not markets:
    raise RuntimeError(
        "no company contracts discovered — check date window, company dict, "
        "or Gamma API availability"
    )

# Guard 2 — classifier never accepted anything as monthly_strike
n_strikes = sum(1 for m in markets if m.contract_family == "monthly_strike")
if n_strikes == 0:
    raise RuntimeError(
        "0 monthly-strike contracts discovered — COMPANY_NAME_PAT may be broken "
        "or date window too narrow; refusing to write"
    )

# Guard 3 — no primary sample (should be same as total since is_primary_sample = classifier-accepted)
n_primary = sum(1 for m in markets if m.is_primary_sample)
if n_primary == 0:
    raise RuntimeError(
        "is_primary_sample count is 0 — contract_family classification is broken"
    )

# Guard 4 — group_ids not assigned (all empty strings)
if all(not m.group_id for m in markets):
    raise RuntimeError("group_id assignment failed — no market carries a group_id")
```

**Summary printout (replace current category table at 01:145–149):**
```
contract_family      total   primary   groups
monthly_strike        XXX       XXX      YYY
corporate_event        XX        XX       ZZ
other                   0         0        0

Top 10 companies by contract count:
  NVDA: 47   TSLA: 38   AAPL: 35  ...

Total markets: NNN
Total groups:  GGG
```

---

## E. Config Changes

### E.1 `config/focal.yaml`

Changes:
- Replace `categories: ["nfl", "nba", "politics", "geopolitics"]` with `categories: []` (or remove the key entirely — script 01 no longer reads it).
- Replace `start_date: "2024-08-01"` with `start_date: "2024-01-01"` (wider default, per direction §4.1 — tunable).
- Replace `end_date: "2025-06-01"` with `end_date: "present"` (or a concrete future date); implement in script 01 as `datetime.now(utc)` when the value is the string `"present"`.
- Remove `market_types.primary` block — no longer meaningful.
- Remove `min_volume_usdc` — no volume floor at discovery.
- Remove `min_market_duration_days` — duration filter eliminated.
- ADD `enumeration_sleep_inter_page: 0.25` and `enumeration_sleep_inter_day: 1.0` as tunable knobs.

**After edit `config/focal.yaml` will look approximately like:**
```yaml
focal:
  start_date: "2024-01-01"
  end_date: "present"
  enumeration_sleep_inter_page: 0.25
  enumeration_sleep_inter_day: 1.0
```

### E.2 `config/categories.yaml` — RETAIN, do not delete

`categories.yaml` is still read by script 05 (news-fetch) for RSS feed URLs and `espn_sport` / `nba_stats` config. Do not delete or modify it. Script 01 simply stops reading it. Add a header comment:

```yaml
# categories.yaml — used by script 05 (news-fetch) for feed configuration.
# Script 01 (discover_universe) no longer reads this file as of Weeks 7-9.
```

---

## F. Downstream Compatibility

### F.1 `scripts/02_pull_trades.py` — no code change required

Script 02 reads `universe.parquet`, filters `is_primary_sample == True` (02:40–44), and iterates rows pulling fills per `yes_token_id` / `no_token_id` (02:58–94).

The partition path at 02:87–90 is:
```python
f"data/polymarket/trades/category={category}/year={year}/month={month:02d}/part-{market_id}.parquet"
```

`category` is read from `row["category"]` (02:63). In the new schema, **`category` is replaced by `contract_family`**. The partition key written on disk must change from `category=` to `contract_family=`. Script 02 must be updated to use `row["contract_family"]` in the path. This is a one-line change at 02:87 — but it is a breaking change to the on-disk partition layout.

**Action required in script 02 before running on new universe:** change `category=` to `contract_family=` in the output path. Mark in the script with a `# W7-9: partition key changed from category to contract_family` comment.

### F.2 `scripts/03_resample_trades.py` — same partition-key update

Script 03 reads trade files via `trades_root.rglob("part-*.parquet")` (03:32) and writes bars at `category={category}/year={year}/month={month:02d}` (03:60). It reads `category` from the universe row at 03:52. Same one-line fix: use `contract_family`. Also a `# W7-9` comment.

**Both 02 and 03 do NOT need deeper refactoring.** They do not reference `market_type`, `SPORTS_CATS`, or `_link_correlated`. The partition-key rename is the only required change.

### F.3 `src/analysis/market_chars.py` — flag for post-EDA update

`market_chars.py:16` hardcodes `_CATEGORY_ORDER = ["nfl", "nba", "politics", "geopolitics"]`. After the new universe is in place, this must become `["monthly_strike", "corporate_event"]` (or derived from `contract_family` values in the data). Do not change now — this module is not on the critical path until scripts 09+. Add a `# TODO W7-9: update _CATEGORY_ORDER` comment at line 16.

### F.4 `src/analysis/purging.py` — flag for post-EDA update

`purging.py:26` hardcodes `_CAT_ORDER = ["nfl", "nba", "politics", "geopolitics"]`. Same fix needed; same deferral. The ridge-regression logic is category-agnostic; only the one-hot expansion at `_one_hot_category` (purging.py:33–36) and the feature-column list at purging.py:29 need updating. Add `# TODO W7-9: update _CAT_ORDER to contract_family values` at line 26.

### F.5 `src/training/dataset.py` — flag for post-EDA update

`dataset.py:9–11` hardcodes:
```python
SPORTS_CATS: frozenset[str] = frozenset(["nfl", "nba"])
CAT_TO_INT: dict[str, int] = {"nfl": 0, "nba": 0, "politics": 1, "geopolitics": 2}
CAT_LABEL: dict[int, str] = {0: "sports", 1: "politics", 2: "geopolitics"}
```

These must become `contract_family`-based mappings. But scripts 15-21 (training) are frozen per the direction document (§4.5). Defer until training resumes. Add `# TODO W7-9: update category maps to contract_family` at line 9.

**Summary of downstream touch-points:**

| File | Action | When |
|---|---|---|
| `scripts/02_pull_trades.py:87` | `category=` → `contract_family=` in path | Before first run of new script 01 |
| `scripts/03_resample_trades.py:52,60` | `category` col → `contract_family`; partition path | Before first run of script 03 |
| `src/analysis/market_chars.py:16` | `_CATEGORY_ORDER` update | Before script 12 (market-chars) |
| `src/analysis/purging.py:26,29,33–36` | `_CAT_ORDER` and one-hot update | Before script 14 (purging) |
| `src/training/dataset.py:9–11` | `SPORTS_CATS`, `CAT_TO_INT`, `CAT_LABEL` | When training resumes (deferred) |

---

## G. Build Sequence and Validation Checkpoint

### G.1 Pre-run steps

1. Confirm `data/.cache/gamma/` exists (or create it). DiskCache (src/utils/cache.py:5) creates subdirs automatically.
2. Set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` (needed only if downstream scripts are run; not needed for script 01).
3. Do NOT set any volume floor in `focal.yaml`.

### G.2 Run script 01

```bash
uv run python scripts/01_discover_universe.py
```

Expected runtime: 20–45 minutes cold (750 days × ~5 pages × 2 passes × 0.25s + DiskCache overhead); < 2 minutes warm (all pages cached).

### G.3 Validation checkpoint — before proceeding to script 02

Run this verification block immediately after script 01 completes:

```python
import pandas as pd
u = pd.read_parquet("data/polymarket/universe.parquet")
cg = pd.read_parquet("data/polymarket/contract_groups.parquet")

# 1. Required columns present
required = {
    "market_id", "contract_family", "company_name", "ticker", "company_id",
    "group_id", "group_role", "strike_price", "strike_direction",
    "price_expiry_month", "volume_1wk", "volume_1mo", "total_volume_usdc",
    "yes_token_id", "is_primary_sample"
}
missing = required - set(u.columns)
assert not missing, f"Missing columns: {missing}"

# 2. No synthetic rows (all market_ids are real conditionIds)
assert u["market_id"].str.len().gt(10).all(), "Short/fake market_id found"

# 3. group_id populated everywhere
assert u["group_id"].notna().all() and (u["group_id"] != "").all()

# 4. Monthly strikes have strike_price and price_expiry_month
strikes = u[u["contract_family"] == "monthly_strike"]
assert strikes["strike_price"].notna().all(), "strike_price null on monthly strikes"
assert strikes["price_expiry_month"].notna().all()

# 5. No old sports/politics markets leaked through
leaked = u[u["company_name"].isna() & u["is_primary_sample"]]
assert len(leaked) == 0, f"{len(leaked)} primary-sample rows missing company_name"

# 6. is_primary_sample matches contract_family
primary_families = set(u[u["is_primary_sample"]]["contract_family"].unique())
assert primary_families <= {"monthly_strike", "corporate_event"}

# 7. _SUCCESS sentinel
from pathlib import Path
assert Path("data/polymarket/_UNIVERSE_SUCCESS").exists()

# 8. Sidecar integrity
assert len(cg) > 0
assert "member_market_ids" in cg.columns
all_member_ids = {mid for ids in cg["member_market_ids"] for mid in ids}
assert all_member_ids <= set(u["market_id"]), "sidecar references unknown market_ids"

print("Validation PASSED")
print(u["contract_family"].value_counts())
print(f"Groups: {len(cg)}, Markets: {len(u)}, Primary: {u['is_primary_sample'].sum()}")
```

Only proceed to script 02 after this block prints "Validation PASSED".

### G.4 Script 02 and 03

Apply the one-line partition-key fix (§F.1, §F.2) to scripts 02 and 03 before running them. No other changes needed.

### G.5 Wipe old artifacts before re-run

```bash
rm -rf data/polymarket/trades/
rm -rf data/polymarket/bars_1min/
rm -f data/polymarket/universe.parquet
rm -f data/polymarket/contract_groups.parquet
rm -f data/polymarket/_UNIVERSE_SUCCESS
# Do NOT wipe data/.cache/gamma/ — keep the page cache for resumability
```

---

## H. Risks and Open Parameters

### H.1 Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `COMPANY_NAME_PAT` regex misses company aliases not yet in dict | Medium | Extend dict iteratively; run classifier on a 100-sample spot-check before full write |
| A given day returns ≥2,100 markets (ceiling hit mid-day) | Low (no day has been observed near this) | Guard in `enumerate_markets`: if `len(page) == page_limit` after 21 consecutive pages (offset=2100), log a loud warning and stop that day-slice; add a narrower time sub-slice as a recovery path |
| Gamma API changes field names (e.g. `volume1wk` → `volume_1wk`) | Low | `get_volume` helper (enumerate_catalog.py:261–269) already tries multiple field names; mirror that in `parse_market` |
| `price_expiry_month` extraction fails for non-standard question phrasings | Medium | Log questions where `extract_strike_fields` returns all-None; manual inspection; fallback to `end_at.strftime("%Y-%m")` |
| Old partition layout (`category=nfl/...`) left on disk confuses script 03 | High (if not wiped) | Mandatory wipe step in §G.5; add check in script 03 that no `category=nfl` or `category=nba` directories exist |

### H.2 Open parameters

| Parameter | Current default | Decision point |
|---|---|---|
| `start_date` | `2024-01-01` | Confirm after EDA shows observation count per contract family |
| `end_date` | `"present"` | Widen or narrow based on GDELT coverage audit |
| Liquidity threshold | None (deferred) | Post-EDA, after log-odds visuals; applies as a post-filter on `universe.parquet`, not a discovery filter |
| Company dictionary source | Promoted from scratch (≈130 names) | Add S&P 500 constituent tickers; private-company names hand-curated |
| `inter_page_sleep` | 0.25s | Can tighten to 0.10s if rate-limit errors are not observed |
| Whether to include `contract_family="other"` rows in universe.parquet | Yes (for completeness) | Could filter to only primary sample before writing; defer to EDA |

---

## I. Novelty-Thread Plumbing Requirements

This section lists the exact fields and artifacts each active research thread requires from the pipeline. Implementers must not remove or rename these fields in scripts 01-03 or any downstream stage without updating this list.

### Thread 1 — Article↔contract matching as embedding-space structure

**What it needs:**

| Artifact / Field | Where it lives | Notes |
|---|---|---|
| `question` | `universe.parquet` | Full contract description text; used as one pole of the embedding-space matching |
| `description` | `universe.parquet` | Additional contract body text |
| `company_name`, `ticker` | `universe.parquet` | Company characteristics used as structured side-information for matching |
| `contract_family`, `price_expiry_month`, `strike_price` | `universe.parquet` | Contract-type metadata; narrows candidate set before embedding comparison |
| `created_at`, `end_at` | `universe.parquet` | Contract date window; used for time-based pre-filtering of article candidates |
| `total_volume_usdc`, `volume_1wk`, `volume_1mo` | `universe.parquet` | Liquidity fields; sanity-check on whether a claimed match is economically relevant |
| `group_id` | `universe.parquet` + `contract_groups.parquet` | Articles matched to a parent group fan out to all child strikes automatically; the group is the unit of article attachment, not the individual strike |
| Article body text | Fetched in scripts 05–06 | Full article body (not just headline/lede); this is a hard requirement per the advisor directive |
| Article `canonical_ts`, `source`, `entity_mentions` | VerifiedArticle schema (existing) | Metadata-first filtering before embedding comparison |

Articles should be attached at the **group level** (one article ↔ one group_id), then the match fans out to all child market_ids sharing that group_id. This must be reflected in the article-market tuple table produced by the matching stage (scripts 08–09), not just in the sidecar.

### Thread 2 — Log-odds reaction over the parent/child strike ladder

**What it needs:**

| Artifact / Field | Where it lives | Notes |
|---|---|---|
| `group_id` | `universe.parquet`, trades partition, bars partition | Must be joinable at every stage: universe → trades → bars → reaction-window tuples |
| `strike_price` | `universe.parquet` | The x-axis of the ladder; must survive into the reaction-window output |
| `strike_direction` | `universe.parquet` | "above"/"below" encoding for monotonicity constraint |
| `price_expiry_month` | `universe.parquet` | Ladder identifier alongside `company_id` |
| `contract_family == "monthly_strike"` filter | Applied in reaction-window stage | Thread 2 applies only to monthly strikes; `contract_family` must be in scope |
| 1-minute bars per child market | `data/polymarket/bars_1min/contract_family=monthly_strike/...` | Log-odds computed per child; group assembled post-hoc by joining on `group_id` |
| `group_id` in bars partition | Requires that script 03 writes `group_id` as a column (not just the partition key) | Confirm script 03 carries through all universe columns when building bars |

**Requirement flagged as research-in-progress:** The formula for the joint strike-ladder log-odds response model is NOT specified here. The requirement is that the plumbing retains `group_id`, `strike_price`, and `strike_direction` from universe through to the reaction-window output, so that the ladder can be assembled for any given (company, expiry_month, article) triple. No architectural assumption about the formula should be baked into scripts 01-10.

### Summary — fields that must survive end-to-end

The following fields must be present in `universe.parquet` **and** propagatable to downstream stages (trades, bars, reaction-window tuples). Any script that rewrites a parquet must carry these columns forward:

```
group_id          # Thread 1 (article fan-out) + Thread 2 (ladder assembly)
company_name      # Thread 1 (structured matching side-info)
ticker            # Thread 1
contract_family   # Thread 1 (candidate pre-filter) + Thread 2 (filter to strikes)
strike_price      # Thread 2
strike_direction  # Thread 2
price_expiry_month  # Thread 2
total_volume_usdc, volume_1wk, volume_1mo  # Thread 1 (liquidity sanity check)
```

`group_id` is the single most critical field: it is the join key that connects a matched article to a full strike ladder. Loss of `group_id` at any intermediate stage forecloses Thread 2 and complicates Thread 1.
