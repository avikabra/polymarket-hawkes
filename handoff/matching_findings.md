# Part I Matching: What the Local Data Shows

*Audit date 2026-11-03. Local data only. No Bouchet access was used. Anything that only Bouchet
can confirm is marked **UNVERIFIED (Bouchet)**.*

## 0. What was measured, and against what

| Source (local) | What it is | Size |
|---|---|---|
| `data/polymarket/universe.parquet` | Current classifier output (script 01) | 6,928 markets, 628 groups, 972 API events |
| `data/polymarket/contract_groups.parquet` | Month-keyed ladder groups | 628 groups (158 ladder groups, 470 standalone) |
| `data/.cache/gamma/` | Raw Gamma API responses from discovery | 9,019 files, 693,180 unique markets (687,522 ending 2024-01-01 to 2026-08-28) |
| `data/polymarket/bars_1min/`, `liquidity_screen.parquet` | Trading panel after the vol > $10k cut | 1,452 markets (1,447 with bars) |
| `data/.cache/gdelt/` | Raw BigQuery GKG result behind script 04 | 546,543 rows, with `V2Organizations` / `V2Persons` offsets intact |
| `data/news/audit/` | Earlier coverage audit tables | uncapped per company-month URL counts, 160-URL body-fetch probe |

All 6,928 universe markets were found in the raw Gamma cache, so every universe row can be joined
to its API fields: `events[0].seriesSlug`, `events[0].slug`, `groupItemTitle`, `endDate`.

**Reference used for disagreement rates.** The series slug was mapped to (company, family) by a
draft lookup I wrote for this audit. That lookup has not been hand-audited yet. Plan §1.3 and §3.1
make the hand audit of disagreements a deliverable. Treat the rates below as measured against a draft
reference, not a gold standard.

Scratch scripts behind every number are in this session's scratchpad (`index_gamma.py`,
`disagree.py`, `expiry.py`, `strike.py`, `enumerate_series.py`, `coverage.py`, `gkg.py`, `gkg2.py`,
`pool_words.py`). They are not committed. Say the word and I will move them into
`scripts/audit/`.

---

## 1. API facts confirmed locally

- `events[0].ticker` equals the event slug for 99.7% of universe rows. It is a slug copy, not a
  stock ticker. Confirmed.
- 93.0% of universe rows (6,443 / 6,928) carry a `seriesSlug`. No market has more than one
  series. `seriesSlug` on the event always equals `series[0].slug`.
- `groupItemTitle` is non-empty on 95.4% of universe rows. On ladders it carries the strike and
  often the direction: `$630`, `↑ $405`, `↓ $252`, `$175B`, `<$6b`, `$2.5b-5b`.
- Market `endDate` equals event `endDate` for 99.7% of rows. Only 1 of 972 universe events has
  members with more than one ET expiry day.
- 975 universe markets end at `04:59:59Z`, which is 23:59:59 ET the previous day. Reading the
  timestamp in UTC moves those markets to the wrong day and, at month ends, the wrong month.

---

## 2. Contract classification failures, with counts

Denominator: the 6,928 accepted markets, unless a row says "pool" (the 687,522 in-window cached
markets) or "API" (the full enumeration in section 4).

### 2a. Wrong company

| Failure | Count | Examples |
|---|---|---|
| Ordinary word matches a ticker alias (case-insensitive regex) | **17** universe rows | `net` matches Cloudflare: Take-Two "net bookings" (5), Interactive Brokers "net interest income" (5), Charles Schwab "core net new assets" (5). `coin` matches Coinbase: "Trump coin" (2) |
| Same failure in the candidate pool, before later filters | **~1,013** of 19,227 pool questions where an alias fires (5.3%) | dash 460 (Houston Dash), net 164 (net worth), cost 107 (eggs cost), coin 83, snow 77 (weather), shop 67 (Temu), ko 20 (tennis player Ko), now 19, hood 12, mu 4 |
| Name alias swallows a different company | **9** rows | "Hewlett" sends Hewlett Packard Enterprise to HP (8). "Square" sends Pershing Square IPO to Block (1) |
| Two-company M&A question goes to whichever name appears first | **8** markets | Qualcomm/Intel, Tesla/xAI (2), SpaceX/xAI, Tesla/SpaceX, Amazon/WBD, Comcast/WBD, Netflix/WBD |
| **Total wrong or ambiguous company** | **34 rows (0.49%)** | |

The misattributions leak into later stages. "block" shows 124 trading company-days in 2024 that
come entirely from the Pershing Square market. Coinbase's trading range starts 2024-06-14 only
because of the Trump-coin market.

Against the series reference, company disagreement on the 6,443 series rows is **3 of the 6,437 series rows with a mappable series company (0.05%)**, all HPE (6 series rows have none). The company errors sit in the 485 series-less rows: **26 of 485 (5.4%)**.

### 2b. Missing stock ticker

3.6% of universe rows have `ticker = None`. 194 of those are private companies, which is
correct. The other ~58 are public companies whose ticker is missing from `COMPANY_DICT`: GS,
C, MS, BA, HD, MA, V, F, AMC, HPE. The question text already holds the ticker in parentheses,
for example "Goldman Sachs (GS)".

### 2c. Wrong contract family

| Failure | Count | Examples |
|---|---|---|
| Non-share-price $ threshold labelled `price_ladder` | **81** of 6,174 price_ladder rows (1.3%) | Bank credit-loss provisions (15), IB fees (10), BlackRock inflows (5), Oracle RPO and capex (8), `*-kpis` series (24), the 15 `net` rows, AirTags retail price (1), "Roaring Kitty YOLO update" (1), Trump coin (2) |
| Netflix Top-10 show/movie markets labelled `corporate_event` | **24** (23 series + 1 series-less) | "Will 'Man on Fire' be the #2 US Netflix show" |
| Earnings-call word-mention markets labelled `corporate_event` | **24** | "Will Tesla (TSLA) say 'Robotaxi'...", Coca-Cola "say 'Ozempic'" (the speech-market exclude regex misses the "(TSLA)" form) |
| IPO-day market-cap ladders labelled `corporate_event` | **~21** (14 series + 7 series-less) | `databricks-ipo-closing-market-cap` (8), `stripe-ipo-closing-market-cap` (6), SpaceX market-cap-at-IPO-month (7) |

Family disagreement against the series reference, on the 6,443 series rows: **61 (0.95%)**.
That is 24 KPI-as-price, 23 Netflix Top-10, and 14 IPO market-cap.

### 2d. Missed contracts: recall, measured against the API

These markets sit inside series the universe already uses, so the company is in the
dictionary, but the classifier rejected them:

| Failure | Count | Cause |
|---|---|---|
| Lower-barrier strikes on `*-hit-price-monthly` ladders | **347** | "Will Meta **dip to** $620 in February?". "dip" is not a direction verb, so `_detect_ladder_metric` returns None. The ladder keeps only its upper half. Same kind of hole in `*-kpis`: 38 more rows ("growth <6%", no `$`) |
| Netflix Top-10 | 1,741 | Correctly out of scope, but excluded only by accident (no family matched) |
| `yearly-ipos` private names | 19 | Brex, Ramp, Discord and others are not in `COMPANY_DICT` |

Whole contract types are missing from the universe. See section 4 for the full table. The
largest are the weekly closing-price buckets (2,440 markets) and the daily up/down binaries
(674).

### 2e. Expiry and grouping (the month problem)

| Failure | Count |
|---|---|
| Ladder groups (`company_metric_YYYY-MM`) that mix **more than one expiry day** | **97 of 158** ladder groups |
| Ladder rows inside those mixed groups | **5,882 of 6,458 (91.1%)** |
| Worst case | `{apple,microsoft,google,nvidia,tesla,amazon}_price_2026-02`: 89 markets, **11 expiry days, 4 series, 11 events** in one "ladder" |
| Groups spanning more than one API event | 109 (6,144 rows) |
| `price_expiry_month` disagrees with the ET month of `endDate` | **450 of 6,458 ladder rows (7.0%)** |
| of which: "finish week of December 29" crosses a month boundary, so the question month is wrong | 285 |
| of which: year fallback taken from the UTC `endDate` ("reach $360 in December" stored as 2026-12, true 2025-12) | 63 |
| of which: valuation ladders whose `endDate` falls the day after the observation date ("by June 30", endDate July 1 12:00 UTC) | 102 |

The last row matters for the plan: `endDate` in ET is the right expiry for price ladders, but
for valuation ladders it is a resolution check time, one day after the observation date. The
date rule has to be family-aware (plan §1.6).

The 972 API events are almost perfectly single-day: one event, one expiry. **The event is the
natural ladder unit.** Ladder rows span **614 distinct events**, against 158 month groups.

### 2f. Strike and direction

- The regex strike agrees with `groupItemTitle` on all but 11 of 6,453 parseable ladder rows.
- Real regex errors: 2 valuation strikes lost their magnitude (Anthropic "$800" read as $800,
  `groupItemTitle` says `↓$800B`; same for Databricks "$250"). 7 Reddit IPO range buckets
  (`$2.5b-5b`) are stored as a single strike at the lower edge. 1 Trump-coin row.
- Direction: 2,085 rows carry an arrow in `groupItemTitle`. Regex disagreement on those: **0**.

---

## 3. Exact training date range (from the data)

The trading panel is the 1,452 markets that pass vol > $10k (1,447 have bars).

| Quantity | Value |
|---|---|
| First trade (ET) | **2024-01-19 15:28** (Reddit IPO valuation / corporate events) |
| Last trade (ET) | **2026-08-26 16:58** |
| 1% / 5% / 10% / 50% of markets start trading by | 2024-08-08 / 2025-09-14 / 2025-10-30 / 2026-01-23 |
| Price ladders, first to last trade | 2024-06-14 to 2026-07-31 (only 2 price-ladder markets before Nov 2025) |
| Months with at least 30 active markets | 2025-04 onward |
| Bulk of activity | 2025-10 to 2026-07 (each month 78 to 429 active markets) |
| Companies with trading | 84 |
| **Company-days with a live market** (union of each market's first-to-last trade day, ET) | **9,548** |
| Company-months those days touch | 489 |
| Existing split (`config/analysis.yaml`) | train < 2026-04-17, val 2026-04-17 to 2026-06-10, test ≥ 2026-06-10 |

The split dates come from `config/analysis.yaml`: train < 2026-04-17, val 2026-04-17 to
2026-06-10, test from 2026-06-10. The 9,548 key set covers the whole panel, first to last trade,
so it includes val and test, and news is needed for all three splits. By split: 7,419 train /
1,057 val / 1,072 test company-days, with 84 companies trading in the train split.

Your "roughly August 2024 through 2026" is right at the edges but not in the middle. Fewer than
1% of markets trade before August 2024, and the panel is thin until September 2025. The current
GDELT pull covers 86 companies × 32 months (2024-01-01 to 2026-08-29). The company-day key set
is 84 companies × 9,548 days.

**Caveat:** this comes from the local bars. Bouchet's universe has the same 628 groups and
6,928 markets according to `reports/bouchet_overnight_run_status.md`, but I could not diff the
bars. **UNVERIFIED (Bouchet)**: that Bouchet's trading panel has the same first and last trades.

---

## 4. API enumeration: every series and series-less event touching our companies

Run over the 687,522 in-window cached markets (the Gamma API as it answered our discovery
pull). 229 of 1,698 series touch a dictionary company.

### 4a. Series-borne contracts

| Type (series pattern) | Series | API markets | API events | In universe | Gap |
|---|---|---|---|---|---|
| Price barrier/strike ladder (`*-multi-strikes-*`, `*-hit-price-*`, `*-hit-month`) | 55 | 6,380 | 541 | 6,033 | 347 "dip to" |
| **Price closing bucket** (`*-neg-risk-weekly`: "close at <$240 on the final day...") | 11 | **2,440** | 222 | **0** | whole type missing |
| **Price daily up/down** (`*-daily-up-down`) | 13 | **674** | 674 | **0** | whole type missing |
| KPI ladder (`*-kpis`, `tesla-deliveries`) | 26 | 280 | 51 | 119 | 161 (non-$ KPIs, dictionary gaps) |
| Earnings (`*-earnings`) | 71 | 147 | 147 | 143 | 4 (`hpq-earnings`: HP Inc ticker missing) |
| Valuation (`*-valuation`, `*-vs-*`) | 7 | 90 | 11 | 88 | 2 head-to-head |
| IPO (`*-ipo*`, `*-closing-market-cap`) | 5 | 53 | 5 | 27 | yearly-ipos privates |
| Netflix Top-10 | 8 | 1,764 | 216 | 23 | should be 0 (not company news) |
| Product / operations (Starship, Waymo, robotaxi, model releases) | 15 | 220 | 39 | 0 | scope decision |
| Person / BTC treasury / other (Musk, MSTR BTC buys) | 12 | 295 | 172 | 1 | out of scope |

### 4b. Series-less contracts

Selection: whole-word, case-sensitive company name in the event title or question, or the
market is already in the universe.

| Type (question pattern) | API markets | API events | In universe |
|---|---|---|---|
| Earnings beat / up-down after earnings (pre-series era) | 143 | 143 | 135 |
| KPI ladders (bank Q2 metrics, Oracle RPO, Micron DRAM, Nike segments...) | 150 | 42 | 128 |
| Price (Coinbase/Robinhood/Apple "hit (HIGH)" in April/May 2026) | 120 | 10 | 61 |
| CEO change | 43 | 15 | 42 |
| IPO date | 51 | 9 | 51 |
| M&A | 25 | 18 | 23 |
| Valuation | 23 | 6 | 15 |
| Market cap | 6 | 5 | 4 |
| Earnings-call word mentions | 896 | 147 | 22 |
| Other (golf "The American Express", "Intel Extreme Masters", Google search rankings, product launches) | 1,101 | 393 | 4 |

Ambiguous names drive 574 of the series-less name hits: Apple 312, Oracle 63, Meta 50, Intel 37,
Dell 24, Ford 19, Uber 19, Nike 18. A name match alone is not a classifier here either.

### 4c. Cross-check against the local universe and groups

| Family | Universe rows | With series | Series-less |
|---|---|---|---|
| price_ladder | 6,174 | 6,057 | 117 (HOOD/COIN/AAPL/META April-May 2026 ladders, plus 57 misfiled KPIs) |
| corporate_event | 470 | 203 | **267** (early earnings, CEO, M&A, IPO, mentions) |
| revenue_ladder | 170 | 95 | **75** (all one-off KPI ladders) |
| valuation_ladder | 110 | 88 | 22 (SpaceX valuation, Reddit IPO buckets) |
| market_cap_ladder | 4 | 0 | 4 (GME, Nvidia 2024) |

Of the 628 groups, 323 are fully series-covered, 7 partly, and **298 have no series at all**
(267 standalone corporate events, 31 ladder groups). **The series method alone would drop 485
universe markets (7.0%) and 298 groups (47%).** What catches them instead is the event: every
series-less market still has an `events[0]` with a slug and title. Plan §1.3 assigns their company
(token, then embedding, then hand review) and §1.4 labels their type once by hand.

---

## 5. GDELT selection: what the local pull shows

Source: the raw BigQuery cache, 546,543 rows, 81 companies, 2024-01-01 to 2026-08-29.

### 5a. The pull is truncated by time of month, not sampled

- The SQL caps each (company, month) at 300 rows with `ORDER BY GKGRECORDID`. That ID starts
  with a timestamp, so the cap keeps the **earliest** 300 records of the month.
- 1,504 of 2,572 company-months hit the cap. **37 of 81 companies hit it every month.**
- In capped company-months, **41.5% of rows fall on day 1**, the median day is the 2nd, and the
  median company-month covers **4 distinct days**.
- So for every large company, the local corpus is essentially "the first few days of each
  month". News shocks after about the 3rd are absent. This alone makes the current corpus
  unusable for an event study keyed to contract days.

### 5b. Alias matching hits other words and other people

The SQL alias regex has no word boundaries and runs over `V2Persons` as well as
`V2Organizations`. On a 100,000-row sample:

| Failure | Rate |
|---|---|
| Company matched **only through the persons field** | 16.3% overall. Uber 90% ("Tommy Tuberville", "Schubert"), Reddit 87%, Dell 83% ("Roger Goodell", "Bank Sabadell"), xAI 81% ("Xaivian Lee"), Ford 71% ("Doug Ford", "Harrison Ford"), Nike 73% ("Nikema Williams") |
| Organization matched **only as a substring** of a longer word | 4.3% overall. Anthropic 87% ("philanthropic"), Intuit 65% ("Intuitive Surgical", "intuition"), Zoom 46% ("Zoomlion", "ZoomInfo"), ARM 30% ("Sinopharm Holdings"), Stripe 17% ("stripe of police") |
| Row matches **more than one** dictionary company | 11.8% (2.6% match three or more). The SQL `CASE` assigns each row to the first company in dictionary order |
| Boilerplate org | Example: a CNN story on elephants is tagged Warner Bros from the "Warner Bros. Discovery Company" footer |

The earlier audit (`reports/gdelt_coverage_audit.md` §4) found only 5% of `meta*` org tokens are
Meta Platforms. The "88.9% agreement" quoted in `company_filter.entity_grounding_match` compares
two substring methods with each other. **It is not a precision number.**

### 5c. Prominence signals already in the pull

The offsets are in the raw cache. The article parquet dropped them (`to_articles` keeps
deduplicated names only), so the rule has to read the raw columns.

| Signal (whole-token org match only) | Distribution |
|---|---|
| Mentions per article | 0: 20.5%, 1: 52.5%, 2: 10.0%, ≥3: 17.0% |
| ≥ 2 mentions | 27.0% |
| First-mention character offset | median 1,004; 25% under 209; 10% under 35 |
| First mention within 500 / 1,000 chars | 28.7% / 39.6% |
| Article length (V2Tone word count) | median 493 words, 90th pct 1,248 |
| Passes "≥ 2 mentions and first mention < 1,000 chars" | **19.7%** (company range 0.2% to 41%) |

These cutoffs are illustrative only. Nobody has measured what they do to precision. The plan
calibrates them.

### 5d. Scale on the panel key set

Using the uncapped per-company-month URL counts from the audit table, prorated to the 9,548
company-days:

| Stage | Estimated URLs |
|---|---|
| Full current scope (86 companies × 32 months) | 20.5M |
| Restricted to panel company-days | **~4.9M** |
| plus whole-token org match | ~4.5M |
| plus "≥ 2 mentions, first < 1,000 chars" | **~1.07M** |
| Share from Google + Meta alone | 67% |

Six company-months have no audit count (AT&T, Block, Coca-Cola, Intel, T-Mobile, Visa, all
dropped as ambiguous), so these are slight underestimates.

### 5e. Body-fetch cost

- Local script 06 measured **~2 bodies/second** at concurrency 16: 1,200 bodies in ~9.8 minutes
  (`logs/script06_run2.log`). At that rate, 475k articles take ~65 hours. That is why the
  pipeline fetched verified matches only.
- Probe yield (160 URLs): aggregator 100%, content farm 100%, long-tail 97.5%, **primary
  journalism 72.5%** (paywalls). Median body 2.4k to 5.2k characters.
- Bouchet: 8,533 / 9,795 verified articles fetched (87.1%). **UNVERIFIED (Bouchet)**: those
  bodies are not local, so I could not inspect them.

---

## 6. Feasibility tests run in this session (local, 2026-11-03)

**Body fetch, 600 URLs.** Up to 12 per company across 68 companies and 373 domains. Drawn from
cached candidates on panel company-days with a whole-token org match.

- Returned a body: 77.8%
- Blocked (403/429): 13.2%
- Gone (404/410): 6.2%
- Timeout or connect error: 1.3%
- Empty: 1.0%
- Other HTTP: 0.5%
- Wall-clock: 52.5 s, which is **11.4 articles/s** (async httpx, 24 global / 2 per-domain).
  Script 06's synchronous fetcher managed about 2/s.
- Median body 3,526 chars. Title and date extracted for every returned body.
- **17.8% of bodies are non-English.** Some returned bodies are the wrong page.

**Contract embedding test.** BGE-large and Wikipedia leads for 94 companies, over 2,854 API
events. Event-level agreement with universe labels: embedding 98.9%, slug 99.7%. Slug coverage
is 93.0% (74.0% on series-less events). Embedding vs slug disagree on 3.2% of the events slug
answers. Detail in plan §1.3.

**Article embedding test.** The 467 fetched bodies, against the same 94 descriptions. Nearest
company agrees with GDELT's tag 37.7% of the time. Median top-2 margin is 0.019. A preliminary
read of 40 articles (one model's labels, not gold) found 22 of 25 disagreements are about none
of our companies. Reweighted, that puts the precision of the GDELT pull itself at roughly 35%.
Detail in plan §2.4.

## 7. Things only Bouchet can confirm (all UNVERIFIED)

1. Bouchet's `universe.parquet` and bars match the local copies row for row. The status report
   says 6,928 markets and 628 groups, but no diff was run.
2. Bouchet's GDELT corpus (546,657 articles) is the same capped pull as the local cache
   (546,543 rows). The 114-row difference is unexplained.
3. The 8,533 fetched bodies: their content, and whether they could seed the hand-labelled
   sample in plan §3.2.
4. `matches.db` on Bouchet: 27,132 candidates "verified" by a rule-based pass, not the LLM.
   Locally only a stale May backup exists.
5. Whether Bouchet compute nodes allow outbound HTTP for bulk body fetching, and at what rate.
6. `parent_event_id` is 100% null in Bouchet's shock-embedding output, per the status report.
   Locally it is populated in `universe.parquet`.

## 8. Contract counts under the revised rules (probe of 2026-11-03)

Counts after steps 1 to 13, for the window ending 2026-10-31:

| Type | Groups | Markets | Markets ≥ $1k | Markets ≥ $10k | Groups with ≥ 3 rungs ≥ $1k |
|---|---|---|---|---|---|
| Price close ladder | 1,941 | 14,327 | 5,281 | 1,022 | 639 |
| Price barrier ladder | 552 | 9,920 | 4,691 | 593 | 468 |
| Weekly closing bucket | 457 | 5,027 | 1,842 | 241 | 198 |
| Earnings | 178 | 178 | 170 | 81 | single market |
| Revenue and KPI | 90 | 466 | 269 | 41 | 52 |
| Valuation | 10 | 70 | 55 | 11 | 10 |
| Total | 3,229 | 29,989 | 12,308 | 1,989 | 1,367 |

The data is thinner than the raw counts suggest, for three reasons.

- Most markets trade very little. 59% traded under $1,000 in total and 93% under $10,000. The
  median market traded $571.
- Volume inside each group sits on a few rungs. The busiest rung holds a median 34% of the
  group's volume, and the top three hold 72%. The far-out strikes draw much of the volume.
- Polymarket's stock contracts are young and concentrated. The liquid markets cluster from
  November 2025 to February 2026, and nine companies (Nvidia, Tesla, Alphabet, Amazon, Meta,
  Apple, Microsoft, Netflix, Palantir) hold 93% of the markets above $10,000.

The plan uses $1,000 as the inclusion floor. That keeps 12,308 markets and 1,367 groups with
three or more active rungs. The $10,000 set (1,989 markets) serves as a robustness check. At
$10,000 alone, the ladders lose most of their rungs, and the strike-ladder structure that the
thesis studies disappears.

These counts support a study centred on the nine large companies, with the other 53 contributing
a thinner tail. I checked whether other Polymarket families hold more measurable contracts with a
news link. Crypto price ladders have the most liquidity (26,319 markets above $10,000), but
crypto has no firm-level news or characteristics, so Kelly's method has nothing to purge
against. Fed, CPI, jobs and GDP contracts (about 300 groups) have exact release dates and a
clean news link, but there are too few to stand alone. Commodity ladders (1,084 markets above
$10,000) have a weaker news link. The plan keeps the stock contracts as the core. The macro
release contracts are the first extension if the stock panel proves too thin in the shock
regression.
