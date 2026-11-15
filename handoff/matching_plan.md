# Part I Matching: Design for Contract Classification and Article Selection

*Planning pass, 2026-11-03. Local only. Nothing in the pipeline is rebuilt by this document.
Evidence for every number is in `handoff/matching_findings.md` (cited as F§n).*

## 0. Summary

**One company registry and description set serves both sides.** Each company gets a text
description and one embedding. Series contracts resolve to a company by the slug token. The
embedding resolves series-less contracts that carry no token, and scores articles among the
companies they name. The fixed company list is the registry of IDs, names and tickers that the
slug rule reads.

| Piece | Today | Proposed |
|---|---|---|
| Contract unit | Regex on question text, grouped by `company_metric_YYYY-MM` | One API **event** = one ladder, one expiry **day** (ET) |
| Contract → company | Case-insensitive alias regex, first hit wins | Slug token for series events (the slug names the company). Embedding proximity (δ ≥ 0.02) for series-less events without a token. Hand review of disagreements (~3%). Tested in 1.3 |
| Contract type | Keyword regex | Series-name suffix (trivial rule) for 93% of rows. One-time labelled set for the series-less remainder |
| Strike / direction | Regex on question | `groupItemTitle` (arrows, `<`, `>`, ranges). Regex only as a cross-check |
| Expiry | Month from question text | `endDate` read in ET, with a family-aware observation-date check |
| Article pull | All 32 months × 86 companies, first 300 rows per company-month | Only panel **company-days**, random rather than time-ordered sampling, whole-token org filter in SQL |
| Embedding model | BGE-large (2023, English-only) | harrier-oss-v1-0.6b (Apr 2026, multilingual, MTEB-Multilingual 69.0 published), run on Bouchet; fallback Qwen3-Embedding-4B (2.11) |
| Article cutoff | none / hand-picked cosine | from a passing-mention null with per-company standardization at a stated error rate q; labels verify only (2.10) |
| Article → company | Substring regex on GKG org/person strings | Full text (headline, lede, body) embedded. Scored only against companies the text names, relative to a background. One fitted probability per (article, company). Multi-label. Plain nearest-of-94 was tested and fails (2.4) |
| Body storage | Not fetched beyond verified matches | Keep bodies for matched articles and audit samples. Keep embeddings and features for the rest (2.7) |
| Accuracy | None measured | Hand-labelled stratified sample grades the full-text matcher; coverage reported on the whole candidate set |

---

## Part 1. Contracts

### 1.1 Unit of analysis: the API event

The month group mixes 11 expiry days and 4 series in the worst case. 91% of ladder rows sit in
groups with more than one expiry day (F§2e). The API event is single-day in 971 of 972 cases.

- **Ladder = event.** `ladder_id = event_id`, `expiry_day = endDate in ET`, members = the event's
  markets, strikes from `groupItemTitle`.
- **Surface = company × contract type × expiry day.** When Thread 2 needs strikes across
  expiries, stack events by `(company_id, contract_type)` over `expiry_day`. This replaces the
  month bucket with something that has a defined time axis.
- The month key goes away. `price_expiry_month` stays only as a derived display field.

### 1.2 Enumeration: everything that touches our companies

Pull every event that ends in the window from Gamma. The local cache already holds a complete
pass: 687,522 markets. A fresh pull is needed only to extend past 2026-08-28. Two routes feed
the candidate list:

1. **Series route.** Every series whose slug carries a company token (1.3); the token gives the
   company. Locally this catches 229 series and 93% of universe rows.
2. **Series-less route.** Every event without a series: slug or name token first, then
   embedding, then hand review (1.3). This catches the remaining 485 universe rows (7.0%) and 298 of the 628 groups
   (F§4c). They are early earnings, CEO, M&A, IPO and one-off KPI ladders. **The series method
   alone misses all of these.** The event-text route catches them.

Every candidate event goes into one table, `contract_events.parquet`, one row per event:
`event_id, event_slug, series_slug, company_id, company_score, company_margin,
company_fallback, contract_type, expiry_day_et, observation_day, n_markets, in_scope`. The table
is small: about 2,850 events in window (2,085 series, 769 series-less; tested in §1.3).
That size makes hand-auditing the uncertain rows practical.

### 1.3 Contract → company by embedding proximity (requested test)

**Tested variant (embedding first, slug fallback).** Embed each company description (2.5) with the same model as the article side. Embed
each event's `title + first question + series slug words`. Assign the nearest company if its
cosine score beats the runner-up by a margin. Two-company events (M&A, mergers, "X vs Y")
can carry both companies and are routed to hand review.

**Tested variant, fallback half.** Slug-token match: a series or event slug token equals a company's lowercase name
or ticker. This is the only hand-maintained piece: one row per company (`company_id`, names,
ticker, Wikipedia title, SEC CIK). It is used when the embedding margin is below the threshold,
and it is always reported next to the embedding result.

**Test result on the local enumeration (run 2026-11-03).** BGE-large; Wikipedia lead sections for
94 companies; 2,854 API events (2,085 series, 769 series-less) covering 14,904 markets; 969 of
them carry universe rows.

| Measure | Embedding | Slug fallback |
|---|---|---|
| Agreement with universe label, all 969 events | 98.9% (99.3% market-weighted) | 99.7% of the events it answers |
| Series events (751) | 99.6% | 100% |
| Series-less events (218) | 96.3% | 98.6% |
| Coverage: share of all 2,854 events given a company | 100% (forced) | **93.0%** (99.95% series, **74.0%** series-less) |
| Embedding vs slug disagreement, where slug answers (2,653) | 3.2% overall (1.8% series, 8.4% series-less) | |

| Margin δ | In-universe events assigned | Accuracy among assigned |
|---|---|---|
| 0 | 100% | 99.3% |
| 0.02 | 92.4% | 99.9% |
| 0.03 | 88.1% | 100% |
| 0.05 | 69.4% | 100% |

The embedding's 7 real errors are all peer or token collisions on very short text:

- "Apple (AAPL) close above" sent to AT&T (margin 0.003 to 0.009)
- "$GME market cap" sent to GM
- "Zuckerberg out as Facebook CEO" sent to Google

The most frequent near-tie pairs are Meta/Reddit, Apple/AT&T, Microsoft/Workday and
Mastercard/Klarna.

The absolute score cannot detect a company outside our list. Take-Two, IBKR and Schwab sit in
the same 0.5 to 0.6 range as correct matches, and no threshold separates them without dropping
most correct events.

The slug agreement is partly circular, because the universe labels came from the same alias
dictionary. The 4 universe errors the embedding exposed (Schwab, IBKR, Take-Two, Pershing
Square) were also wrong under slug.

**Decision for contracts.** The embedding is not better than the slug where the slug answers.
For series it adds nothing: the series slug *is* the company (`apple-hit-price-monthly`). It
earns its place only on the 26% of series-less events where no slug token matches. Rule:

1. Series events: slug token. A one-line rule against the company registry, not a mapping table.
2. Series-less events: slug or name token if present. Otherwise the embedding with δ ≥ 0.02.
3. Everything else, plus every slug/embedding disagreement: hand review. Measured size:
   about 3% of events, roughly 90 rows. The out-of-list cases (Take-Two, Schwab) land here, and
   review drops them.

Report the embedding-vs-slug disagreement table with every rebuild. That is the measured
accuracy that does not exist today.

### 1.4 Contract type

The type split needs no learning for 93% of rows. The series slug ends in one of about 10
suffixes, and each suffix is one line of code:

| Suffix | Type |
|---|---|
| `multi-strikes-{weekly,monthly}` | `price_close_ladder` (finish above $K at expiry) |
| `hit-price-{weekly,monthly}`, `hit-month` | `price_barrier_ladder` (touch $K any time before expiry, both ↑ and ↓) |
| `neg-risk-weekly` | `price_close_bucket` (mutually exclusive closing ranges) |
| `daily-up-down`, `up-or-down`, `closing-price-*` | `price_up_down` (single binary vs. reference close) |
| `kpis`, `deliveries` | `kpi_ladder` |
| `earnings` | `earnings_beat` |
| `valuation`, `-vs-` | `valuation_ladder` / `valuation_pair` |
| `ipo`, `closing-market-cap` | `ipo_event` / `ipo_mcap_ladder` |

Note the split the old regex hid: **barrier** and **close** ladders are different payoffs. A
digital barrier and a digital close at the same strike are not the same contract, and the
Thread 2 structural model has to know which one it is pricing.

For the **series-less** events (218 in the universe, about 770 candidates in window), the options are:

| Option | Cost | Risk |
|---|---|---|
| A. Hand-label each event once into the same type list, stored as an auditable CSV | ~2 hours for ~770 rows | none beyond labeller error. One-time, since series-less events are the API's older, non-recurring style |
| B. Embed type prototypes ("quarterly revenue threshold", "CEO departure"...) and assign by proximity | ~1 hour build | prototype wording drives results. Still needs a hand check |
| C. Keep question regex | 0 | the failures in F§2c |

**Recommendation: A.** It is a label set, not a prescriptive mapping. It is small and finite,
and it doubles as the gold standard for checking B if B is ever wanted for live data.

**Scope decisions you need to make** (counts are API markets in window, F§4a):

- **Include** `price_close_bucket` (2,440) and `price_up_down` (674). Both are share-price
  contracts on our companies and are currently missing entirely. Buckets are a ladder in
  negRisk form. Up/down is one strike at the money.
- **Include** the 347 "dip to" lower barriers. Without them the barrier ladders are one-sided.
- **Exclude** Netflix Top-10 (1,764), earnings-call word mentions (~900), and person/BTC series
  (295). None of them are about the company's value.
- **Decide:** product/operations events (220: Starship launches, Waymo cities, robotaxi, model
  releases). They are company news shocks, but they are not valuation contracts. I lean
  exclude for Part I, but it's your call.

### 1.5 Strike and direction

Parse `groupItemTitle`:

- `↑`/`↓` → direction
- `<$X`/`>$X` → bucket edge
- `$A-B` → range bucket with both edges stored
- magnitude suffix `B`/`T`/`M`/`b`, case-insensitive

Use the question regex only when `groupItemTitle` is empty (4.6% of rows) and as a cross-check.
Measured locally: 11 disagreements out of 6,453, 2 of them real regex magnitude losses
(F§2f). Range buckets must become `(lo, hi)`, not a single strike.

### 1.6 Expiry day

- `expiry_ts = endDate`, converted to `America/New_York`. `expiry_day = its date`. Never read
  the month or day in UTC: 975 markets end at 23:59:59 ET, which is 04:59:59Z the next day.
- `observation_day` differs from `expiry_day` for valuation ladders. "By June 30" resolves on
  July 1 at 12:00 UTC (102 rows, F§2e). Rule: if a question carries an explicit date ("by June
  30", "on May 17"), parse it. If it disagrees with `expiry_day` by exactly one day and the
  family is valuation or IPO, take the question date as `observation_day`. Report every other
  disagreement for review rather than resolving it silently.
- `week of …` questions: trust `endDate`, never the question month (285 rows were wrong).

### 1.7 Cross-check against today's universe (acceptance test)

Rebuild the event table, then reconcile with `universe.parquet` (6,928) and
`contract_groups.parquet` (628):

| Expected difference | Approx. count | Direction |
|---|---|---|
| New price buckets, up/down, "dip to" | ~3,460 | added |
| Netflix Top-10, mention markets | ~48 in universe | dropped |
| Wrong-company rows (`net`, `coin`, Square, Hewlett) | 26, plus 8 two-company M&A markets | company corrected or dropped |
| KPI rows labelled `price_ladder` | 81 | type corrected |
| 628 month groups | → ~1,900 events (972 in universe + ~222 bucket events + ~674 up/down events, minus dropped Netflix/mention events) | regrouped |

Any universe row that disappears for a reason not on this list is a bug in the rebuild.

---

## Part 2. Articles

### 2.1 The pull: company-day, not month

**Key set.** For each market in the vol > $10k panel, take every ET day from its first trade to
its last trade. Union by company → 9,548 company-days, 84 companies (F§3). The key set covers the whole panel, so train, val and test. Add a pre-window
lookback of N days (default 3) so a shock that lands just before a market opens still has
context. Collapse each company's days into contiguous intervals.

**Query.** One BigQuery job per batch of intervals against `gkg_partitioned`, pruned on
`_PARTITIONTIME` to the union of days, joined to an in-query table of `(company_id, day)`:

- Candidate filter in SQL: whole-token, case-sensitive alias match against **`V2Organizations`
  only**. Not `V2Persons`, which caused 16% of matches: Tuberville, Goodell, Harrison Ford.
  Word boundaries go into `REGEXP_CONTAINS`. This is a recall filter, not the decision. The
  decision is the full-text matcher (2.4).
- Ambiguous aliases (Apple, Meta, Oracle, Stripe, Visa, Intel...) are **kept** in SQL as whole
  tokens. The embedding matcher, not an exclusion list, now handles ambiguity. Today's exclusion
  list silently removes Intel, Visa, AT&T, Coca-Cola, T-Mobile and Block from the corpus.
- No first-match `CASE`. Emit one row per (record, company) so a record mentioning two
  companies reaches both.
- Drop the per-company-month cap ordered by `GKGRECORDID`. That cap returns the first days of
  each month (41.5% of rows on day 1, F§5a). If a cap is needed, apply it per **company-day**
  and order by `FARM_FINGERPRINT(GKGRECORDID)`, which is uniform random and reproducible.
- Keep the content-farm domain exclusion and the existing budget gate (dry-run, $25 hard
  ceiling).
- Add a URL dedup and a syndication dedup (same normalized title on the same day keeps one).

**Cost.** Scan cost is set by the days touched and the columns read, not by the filter. The
key-set days span 2024-01-19 to 2026-08-26, but are dense only from 2025-09. The audit
(reports/gdelt_coverage_audit.md §0) measured $2.72 for a 7-column scan of all 32 months; the
current pull reads 10 columns. The day-pruned scan is lower. Exact number:
dry-run before any run (no estimate replaces the dry-run).

**Volume** (F§5d): ~4.9M URLs on panel company-days, ~4.5M after whole-token org matching.
Google and Meta are 67% of it. That volume, not the query, drives the cost of the next step.

### 2.2 What the GKG record gives us, and what the design uses

GKG 2.1 fields (codebook names; BigQuery column names in parentheses where different). The
current pull reads 10 of them.

| Field | Contents | Use? | Why |
|---|---|---|---|
| `GKGRECORDID` | `YYYYMMDDHHMMSS-n` | **use** | key; random-order hash for sampling |
| `DATE` / `_PARTITIONTIME` | crawl time, 15-min batch | **use** | day key (day precision only, per CLAUDE.md) |
| `SourceCommonName`, `DocumentIdentifier` | domain, URL | **use** | fetch target; source stratum; content-farm filter |
| `SourceCollectionIdentifier` | web, broadcast... | **use (filter)** | keep web (1) only. Not read today |
| `V2Organizations` (`V2EnhancedOrganizations`) | org name + char offset, once per mention | **use** | SQL recall filter; mention count and first offset serve as fetch priority and sampling strata before the fetch, and body-derived counts replace them after |
| `V1Organizations` | deduplicated names, no offsets | drop | strictly less than V2 |
| `V2Persons` | person + offset | **drop for matching**, keep as a column | substring hits on surnames caused 16% of matches. Useful only if a later step wants executives, which this design does not need |
| `AllNames` | every proper name incl. products, with offsets | **use as a recall audit of the org filter (not a production filter)** | catches companies GKG did not tag as an org ("ChatGPT maker OpenAI"); recall check on the SQL filter |
| `V2Themes` | taxonomy codes + offsets (`ECON_STOCKMARKET`, `WB_…`) | **use as a feature**, not a filter | measures whether an article is business news; candidate stratum for the labelled sample |
| `V2Tone` | tone, pos, neg, polarity, activity, self-ref, **word count** | **use** | word count normalizes mention density; tone is a shock covariate later |
| `V2Counts`, `Amounts` | counted objects, numeric amounts with offsets | drop for matching | earnings figures and deal sizes are interesting for Part II, not for assignment |
| `V2Locations` | geo + offsets | drop | no role in company assignment |
| `GCAM` | ~2,300 dictionary scores | drop | large column, cost for no matching value |
| `Dates`, `Quotations` | dates and quotes mentioned in text | drop for now | `Dates` could flag stale/retrospective stories; revisit in Part II |
| `SharingImage`, `RelatedImages`, social embeds | image/video URLs | drop | no value |
| `TranslationInfo` | source language / engine | **use (filter)** | English-model embeddings need English text; route non-English to a multilingual model or drop. This field says which |
| `Extras` | XML; includes `<PAGE_TITLE>` for most web docs | **use** | free headline without fetching; the fallback text when a body is blocked (2.3) |

§2.8 judges each field's worth once decisions move to the body.

*Two of these are **UNVERIFIED** against the live table. Column availability in
`gkg_partitioned` for `AllNames`, `TranslationInfo`, `Extras`/`PAGE_TITLE` needs one free
schema lookup (`bq show --schema`, zero bytes billed) before the SQL is written.*

### 2.3 Body fetch: measured feasibility and the fallback

**Measured today** (local laptop, 600 URLs, ≤12 per company across 68 companies and 373
domains, from panel company-days with a whole-token org match; F§6):

| Outcome | Share |
|---|---|
| Body returned (≥300 chars) | **77.8%** (median 3,526 chars; title and date extracted for 100%) |
| Blocked (403/429) | 13.2% (benzinga alone is 20 of 79) |
| Gone (404/410) | 6.2% |
| Timeout / connect error | 1.3% |
| 200 but empty | 1.0% |
| Other HTTP | 0.5% |
| **Throughput** | **11.4 articles/s** wall-clock (async httpx, 24 global / 2 per-domain concurrency, trafilatura extraction) |

Two quality catches: **17.8% of returned bodies are not English**, and some returned bodies are
the wrong page (boilerplate, or an essay under an Intuit headline). "Fetched" does not mean
"usable".

**What the rate means at scale** (single machine, same settings):

| Candidate set | Bodies needed | Time at the measured rate |
|---|---|---|
| Labelled sample + automated check (3.2, 3.3) | ~20k | under 1 hour |
| Prominence-ranked top 20 per company-day | ≤ 191k | ~5 h |
| Strong-rule pass (F§5d) | ~1.07M | ~26 h |
| All whole-token candidates | ~4.5M | ~4.6 days |

The old estimate (65 hours for 475k) came from the synchronous fetcher in script 06 at about
2/s. The async probe ran at 11.4/s with per-domain politeness. The bottleneck is per-domain
rate limits, not bandwidth. A few domains (yahoo, biztoc, benzinga) hold a large share of URLs,
and they rate-limit (429) and block (403) first.

**Bouchet.** **UNVERIFIED (Bouchet):** whether compute nodes have outbound HTTP, and at what
rate. If they do, shard by domain across array jobs. If they do not, the fetch runs locally (or
on a small cloud VM) and only the bodies move to Bouchet. The design does not depend on Bouchet
for fetching. At the measured rate, a laptop finishes the 191k tier overnight.

**Fallback ladder** when a body cannot be fetched (about 22% of URLs):

1. **Page title from `Extras/PAGE_TITLE` plus URL slug** (a title only, no lede) → embed that
   shorter text, mark `text_source = "title_only"`. It enters the fitted probability with a
   `title_only` indicator, calibrated separately on the labelled sample, since title-only
   accuracy will differ.
2. **Archived copy** (Wayback `id_` snapshot) for 403/404/410 from high-value sources only.
   Measured cost first: probe 100 before committing.
3. **Drop**, with the drop recorded. Report coverage by source bucket so a reader sees which
   publishers are underrepresented (paywalled primary journalism is the most affected: 72.5%
   yield in the earlier probe).

Every article carries `text_source ∈ {full_text, title_only}`. Accuracy is reported separately
for each.

### 2.4 The matcher: full text, embedding, margin

**Representation.** `text = headline + "\n" + lede + "\n" + body`, capped at 512 tokens.
The cap keeps cost and comparability fixed: it covers the headline, lede and opening paragraphs,
where subject information concentrates. The chosen model accepts 32K tokens, so the cap can be
raised later if the audit shows late-subject articles are lost. The company side is one
description per company (2.5). The same model is used on both sides. This is the **matching**
model (`microsoft/harrier-oss-v1-0.6b`, 2.11), never the Part II analysis model (E5), per the
CLAUDE.md invariant. All local tests in this document used BGE-large, the model already on the
machine.

**Tested and rejected: plain nearest-of-94 with margin gate (results below).** Score
`s(a,c) = cos(e_a, e_c)` against all 94 descriptions and assign the top company when its score
clears an absolute floor `τ_abs` and beats the runner-up by a margin `δ`, with a two-company
exception, a peer guard and a live-market restriction, all set on the labelled sample (3.2) at a
fixed precision target. The first test below shows this rule fails, and the revised matcher
replaces it.

**Model choice.** Decided by the benchmark in 2.11, before any full run, so nothing is
embedded twice. Chosen: harrier-oss-v1-0.6b, with Qwen3-Embedding-4B as the fallback.

**Embedding cost.** One BGE-large pass over 467 bodies, 94 descriptions and 2,854 contract
events ran on Apple MPS in one background job of a few minutes, including the model download.
I did not time it per article. Fetching, not embedding, is the bottleneck at every tier.

**First test on articles (467 fetched bodies, unlabelled, plus a 40-article preliminary read).**
This test changed the design:

| Measure | Value |
|---|---|
| Embedding's nearest company = GDELT's company | 37.7% (80% when s1 ≥ 0.65) |
| Rank of GDELT's company among 94 | 1st 37.7%; beyond 10th 37.5% |
| Margin s1 − s2 | median **0.019**; p25 0.008 |
| Assigned at δ = 0.02 / 0.03 / 0.05 | 49% / 40% / 29% |
| Of those unassigned at δ = 0.03, both top-2 companies named in the text | 4.6% |
| Preliminary read, 25 disagreements: about GDELT's company / the embedding's / **neither** | 2 / 1 / **22** |
| Preliminary read, 15 agreements: correct / neither | 12 / 3 |
| Non-English bodies | 17.8%; agreement 17% vs 42% for English |

What it shows:

1. **Most GDELT candidates are about none of our companies.** That holds even after the
   training-day and whole-token filters. Reweighting the preliminary read by the 38/62
   agree/disagree split puts the precision of the pull itself at roughly **35%**. This is one
   model's labels on 40 articles, not a result, but it is the first number anyone has had.
2. **Nearest-company assignment has no "none" option.** Market wraps, BizToc ticker pages and
   generic AI pieces land on hub companies: Anthropic takes 49 of 467 and Robinhood 24, at
   margins near 0.01.
3. **Absolute score does not separate "none".** Off-topic articles have median s1 0.58, against
   0.64 for on-topic ones. s1 < 0.52 catches 8 of 25 off-topic articles with no false positives,
   and misses the rest.
4. **The margin mostly removes junk, not partnership stories.** Only 4.6% of what δ = 0.03 drops
   names both companies. It also drops real ones: a Unit 42 story on Palo Alto at margin 0.003.

**Revised matcher (supersedes the plain argmax above):**

1. **Candidates first.** An article is scored only against companies it names: whole-token
   company names counted **in the fetched body**, unioned with GKG org hits, restricted to
   companies with a live market that day. That is the list we already keep, one row per
   company, not a catalog. This removes the hub problem: Anthropic cannot win an article that
   never names it.
2. **"About the company" is a separate decision from "which company".** Score each candidate
   pair by its similarity *relative to* a background:
   `r(a,c) = cos(e_a, e_c) − mean_k cos(e_a, e_k)` over all 94 descriptions. This removes
   the article-level offset that made absolute cosine useless: generic finance pages score high
   against everything. It is one score, with no fitted weights. Body-name share and
   first-mention position are reported alongside r. They are not combined into a model fitted
   on labels, because the labels do not choose anything (2.10).
3. **Multi-label, cutoff from a null.** Keep every candidate whose r clears the cutoff. The
   cutoff comes from the null distribution in 2.10, never from the labelled sample.
   Partnership stories get both companies without a special case. The margin is not a gate.
4. **Language.** Route non-English bodies (from `TranslationInfo`, or language detection on the
   body) to a multilingual embedding model, or drop them. Measure which costs less coverage on
   the labelled sample.
5. **Dedup before scoring.** The same BizToc page appeared under 4 companies, and 38 of 467
   titles are duplicates.

The labelled sample verifies the result (3.2). It does not tune it. The test shows the
plain-argmax version would fail any reasonable precision target.

### 2.5 Company descriptions: Wikipedia vs filings

| Source | Coverage | Strength | Weakness |
|---|---|---|---|
| Wikipedia lead section | all 94 companies, incl. private (OpenAI, SpaceX, Stripe, Anthropic, Databricks, xAI, Waymo) | one free API call each; written for disambiguation ("Apple Inc. is an American multinational technology company…") | general; includes history and controversies that pull embeddings toward non-business topics |
| 10-K Item 1 "Business" (SEC EDGAR, by CIK) | public US filers only (~80); foreign filers use 20-F (TSMC, ARM, Shopify) | the firm's own segment and product language; matches how earnings and KPI stories are written | long (truncate to the first ~2k chars or the segment overview); none for private companies |
| S-1 / company "About" page | private and recent IPOs | fills the filing gap | uneven, marketing tone |

**Comparison protocol.** Build both description sets. Use Wikipedia for private companies in
both arms, so the comparison isolates public companies. Run the matcher with each set on the
labelled sample. Report precision, recall and F1 per arm, overall and on the peer pairs. Pick
the winner, or average the two embeddings if neither dominates (cheap, often better). The
description text is stored and versioned, because it is now a model input.

### 2.6 Weighing the alternatives honestly

| Approach | Needs per-company catalogs? | Needs bodies? | What it misses | Verdict |
|---|---|---|---|---|
| Headline/offset rule (≥2 mentions, early mention), my previous draft | no | no | judges from GKG's org strings, whose own accuracy is unmeasured; cannot tell "Apple" the subject from "Apple" the app-store mention | **replaced**; its offsets survive only as sampling strata and features |
| Co-occurrence with executives, products, tickers | **yes**, per company, maintained over time | no | anything the catalog lacks (new products, new CEOs); this is exactly the hard-coded list you rejected | **rejected** |
| Full-text embedding vs company description, plain nearest-of-94 | no (one description per company) | yes | has no "none" option; generic pages land on hub companies; peers tie (tested, 2.4) | **rejected as tested** |
| Full-text embedding, candidates restricted to named companies, background-relative score, fitted probability (this plan) | no (company names only, which the registry already holds) | yes | title-only and non-English text; truncation | **chosen, pending the labelled sample** |
| LLM judge on the body ("is this article primarily about X?") | no | yes | cost per article at 1M scale; prompt drift | **used as the large-sample automated check (3.3), not as the matcher** |
| NLI / zero-shot classifier | no | yes | slower than embeddings, no better on subject-vs-mention in my experience; untested here | not pursued unless the embedding matcher fails its precision target |

The honest cost of the chosen method is fetching. It needs bodies for every candidate. 2.3
shows that is feasible at the 191k tier in an overnight run, and the fallback handles the
rest.

### 2.7 Fetch, embed, discard: judged

**The proposal:** fetch the body, embed it, keep the embedding and scores, discard the body.

**The storage it saves is small.**

| Item | Size at 1M articles |
|---|---|
| Bodies, median 3.5k chars (zstd parquet) | ~1.5 to 2 GB, ~4 GB raw |
| BGE-large float16 embeddings | ~2 GB |
| Scores and metadata | <0.2 GB |

The embedding you keep is about as large as the body you discard. Storage is not the reason to
discard. The real reasons are hygiene and redistribution (scraped publisher text should not
travel with the repo or to collaborators) and keeping Bouchet project space small.

**The catches.**

| Catch | How bad | Evidence |
|---|---|---|
| No re-embedding with another model | Real. The plan already calls for benchmarking two models (2.4) and possibly a multilingual one. Each switch means a re-fetch | — |
| Re-fetch is not the same as the first fetch | **Worse than it looks.** Links rot, pages change, blocks tighten | 6.2% of URLs were already 404/410 at fetch time. The earlier 160-URL probe and today's 600 differ on the same domains (iheart, yahoo). Re-fetch yield falls over time |
| No re-reading to audit a match | Real. Neither the labelled sample nor any audit of a disputed match can be read back. The matched set is exactly what a thesis committee will ask to see | — |
| Part II cannot use the stored embedding | **Decisive.** Part II's shock uses the *analysis* embedding (E5-large, float32, 768-dim), which by the CLAUDE.md invariant is separate from the *matching* embedding (BGE, 1024-dim). The stored BGE vector cannot serve Part II. Part II needs E5 over the body, `max_body_chars` 2048 | `config/analysis.yaml` |
| Body features for the revised matcher (2.4: body name counts, first position) | Fine, if computed at fetch time and stored as columns | — |

**The middle option, judged better:**

1. **Keep compressed bodies for every article assigned to a company with a live contract.**
   Expected size is the matched set, ~10 to 20% of candidates if the preliminary ~35% pull
   precision and the margin numbers hold. At the 191k tier that is ~20 to 40k bodies, under
   200 MB. Part II runs E5 on these directly, with no re-fetch and no link-rot loss.
2. **Keep the labelled sample, the 20k automated-check sample, and a fixed random 2% reservoir
   of unmatched candidates.** That is what any later re-calibration or model swap needs. A full
   re-fetch is then only needed to re-score unmatched articles, which a model swap does not
   normally require.
3. **For everything else, keep** URL, URL hash, `PAGE_TITLE`, fetch status, language, the BGE
   embedding, candidate scores and body-derived features. Discard the body.
4. Bodies live outside git under `data/news/bodies/` (already gitignored), never in a shared
   artifact.

Fetch-embed-discard *for all* is acceptable only for the unmatched remainder, and that is what
the middle option does.

### 2.8 GKG fields against the embedding design

What each field is worth once the decision is made from the body:

| Field | Role in this design | Worth |
|---|---|---|
| `DATE` / `_PARTITIONTIME` | Day key, partition pruning | **Essential.** Makes the day-level pull possible and cheap |
| `DocumentIdentifier` (URL) | Fetch target, dedup key | **Essential.** Without it there is no body |
| `SourceCommonName` | Content-farm filter, source stratum, per-domain fetch scheduling | **High.** Drives fetch politeness and coverage reporting |
| `V2Organizations` (strings + offsets) | **Candidate generation:** the only cheap, pre-fetch way to pick which of ~10M daily records to fetch at all. Mention count and first offset become sampling strata and fetch priority within a company-day | **High, but only before the fetch.** After the fetch, body name counts replace them as features. They no longer decide anything |
| `Extras` → `PAGE_TITLE` (unverified column) | Title dedup before fetch (BizToc-style repeats), title-only fallback text | **High** if present: avoids fetching duplicates |
| `TranslationInfo` (unverified column) | Language routing before fetch | **Medium.** Saves fetching 18% non-English if we decide to drop them |
| `V2Themes` | Cheap pre-fetch prior: business/market codes (`ECON_STOCKMARKET`, `ECON_EARNINGSREPORT`…) | **Low to medium, untested.** Could down-rank obvious non-business records (crime, sports) before fetching. Worth one check on the labelled sample. Not a filter until measured |
| `V2Tone` | Word count is a fetch-skip hint (very short pages are usually tickers or stubs) | **Low for matching.** Tone is a Part II covariate, not a matching signal |
| `V2Persons` | — | **None. Harmful as a filter** (16% of matches were surname hits). Executives are not needed: the body text carries them |
| `AllNames` | Recall audit of the org filter (catches untagged mentions) | **Low.** An audit tool, not a production filter |
| `V2Counts`, `Amounts`, `V2Locations`, `GCAM`, `Dates`, `Quotations`, images | — | **None for matching.** `Amounts` and `Dates` may matter for Part II; do not pull them now |

**The organization strings are still for one thing: deciding what to fetch.** Every later
decision moves to the body.

### 2.9 The embedding design: strengths and shortcomings, plainly

**Strengths**

- No per-company catalog. One description per company, and one company registry and description set serves both
  sides.
- On contracts it fills the 26% of series-less events with no slug token, at 99.9% accuracy
  with δ = 0.02.
- On articles, when it is confident and the article is about a listed company, it agrees with a
  correct GDELT label (80% agreement at s1 ≥ 0.65).
- It reads the whole text, so it can tell the subject from a passing mention in principle, which
  no string rule can.
- Multi-label falls out naturally once scores are calibrated probabilities.

**Shortcomings, measured where possible**

1. **No "none" class.** Nearest-of-94 always answers, and absolute cosine does not tell
   on-topic from off-topic (medians 0.64 vs 0.58, overlapping). This is the largest failure in
   the test, and the reason for the candidate restriction and background-relative score in 2.4.
2. **Similar companies sit close.**
   - Description cosines: Ford/GM 0.86, Visa/Mastercard 0.85, AMD/Intel 0.85, SpaceX/xAI 0.85,
     JPMorgan/Morgan Stanley 0.84, OpenAI/Anthropic 0.80, Google/Microsoft 0.76.
   - Peers produce the near-ties: Meta/Reddit, Apple/AT&T, OpenAI/Anthropic. Generic text drifts
     to hub companies.
   - Candidate restriction (the article must name the company) removes most of this. What
     remains is the peer pair named in the same story, which is the multi-label case.
3. **What the margin rule costs.**
   - Contracts: δ = 0.02 leaves 7.6% of in-universe events unassigned and leaves 0.1% error among assigned (100% at δ = 0.03).
     That costs little, because those rows go to hand review.
   - Articles: median margin is 0.019, so δ = 0.02 discards **51%**. Most of that is junk (only
     4.6% are named two-company stories), but real single-company stories are lost too.
   - A margin gate on articles is too blunt. Make it a feature in the fitted probability, not a
     hard cut.
4. **Description choice moves results.** Wikipedia leads include history and controversy text.
   Untested against filings. That is the 2.5 comparison.
5. **Language.** 17.8% non-English with an English model, and agreement drops from 42% to 17%.
6. **Truncation.** 512 tokens covers the lede and opening. Long features with the company late
   are under-weighted. That is acceptable for "primary subject", and wrong for
   "substantive secondary". The labelled sample will show it.
7. **Fetched text is not always the article.** Wrong-page and boilerplate bodies get embedded
   as if real. Dedup and a minimum-length check catch some, but not all.
8. **Circularity on contracts.** The universe labels came from the alias dictionary, so slug
   agreement overstates slug accuracy. Only a hand audit of the disagreements breaks that
   circularity.

### 2.10 The cutoff: set by a null distribution, verified by labels

A cutoff picked off the hand-labelled sample is as arbitrary as the old 0.50 cosine rule. The
cutoff instead comes from data that need no labels.

**Two distributions, both label-free.**

- **Observed:** r(a,c) for every candidate pair, meaning company c is named in article a. This
  is a mixture of true matches and passing mentions.
- **Null:** r(a,c′) for companies c′ the article does **not** name. By construction these are
  non-matches. Two versions, because an easy null flatters the cutoff:
  - *N1, all unnamed companies.* The easy null.
  - *N2, peer null.* Unnamed companies that are peers of a named candidate (top-decile
    description similarity: Ford for a GM story, Mastercard for a Visa story).
  - *N3, passing-mention null (the one carried forward, per the test below).* Named pairs
    where the company appears exactly once, not in the title, and only after the first 1,000
    characters of the body. Text position alone defines it, with no labels. It models the
    real error mode: a company that is named but is not the subject. The circularity risk is
    that a true match mentioned once, late, would be counted as null. Only the labelled sample
    can test that assumption.
  - Scores enter as **per-company standardized** z = (r − median_N1(c)) / IQR_N1(c), because
    company descriptions sit at different distances from everything (7 of 94 companies had
    null shifts larger than their own IQR).

**Where the cutoff goes.** Two label-free rules. Report both, and how far apart they are.

1. **Error-rate rule (two-groups / local false-discovery-rate).** Estimate the null density f₀
   from N2 and the observed density f from candidate pairs. Estimate the null share π₀ from the
   lower tail of the observed scores, where nearly everything is null. Then
   fdr(t) = π₀ f₀(t) / f(t), and the cutoff t* is the lowest score where fdr falls below a
   stated error rate q. The thing being chosen is an **error rate**, which can be defended in
   one sentence ("we accept 1 in 10 assigned pairs being wrong"). It is not a cosine value.
   q is your decision (Part 6).
2. **Break rule.** If the observed distribution is clearly bimodal (dip test p < 0.01; two-
   component mixture beats one by BIC), the antimode is a natural break. Use it only if it
   lands near t*. A break nowhere near t* means the distribution does not break cleanly, and
   rule 1 stands.

**Per-company or pooled.** Fit pooled first. Then check for systematic shifts of the null by
company (some descriptions sit closer to everything). If any company's null median is off by
more than its own IQR, use a per-company null for that company only.

**The labelled sample's job: verification only.** With t* fixed in advance:

- Report realized precision and recall at t*, with CIs.
- Report realized error rate against the target q.
- If realized precision misses the target, report that as the result. Do not move t* to fit.

The null may be too easy even as N2, because passing mentions are a harder non-match than
unnamed peers. Realized precision below 1 − q is that failure, measured.

**Audit the cut.** For pairs inside vs outside t*, tabulate share and counts by:

- company
- month
- source bucket (primary / aggregator / long-tail / content farm)
- language
- `text_source` (full_text / title_only)
- score band (deciles of r)

Flag any cell where the inside share departs from the pooled share by more than 2 standard
errors. Those cells are where the cut is doing something company- or source-specific, and they
go into the error analysis.

**Show the labelled sample is representative.** On the same dimensions, compare the labelled
sample's distribution to the full candidate set: standardized differences per category, and a
KS test on r. Stratification (3.2) deliberately over-samples some cells, so compare after
applying the sampling weights. Report the weighted comparison. Any dimension with a
standardized difference above 0.1 after weighting gets more labels before the verification
counts.

**Test result on the 467-article subset (label-free cutoff; ~40 weak model-made labels used
only to verify; run 2026-11-03 on BGE-large scores already on disk).**

Population: 943 candidate pairs, meaning company named in the article, across 388 articles.
Nulls: N1 42,955 pairs, N2 6,536, N3 458.

| r distribution | 5% | median | 95% |
|---|---|---|---|
| Observed candidate pairs | −0.019 | 0.048 | 0.221 |
| N1 (all unnamed) | −0.063 | −0.002 | 0.063 |
| N2 (unnamed peers) | −0.038 | 0.019 | 0.089 |
| N3 (passing mention) | — | 0.024 | 0.113 |

Separation of observed pairs from each null (AUC): 0.80 vs N1, 0.69 vs N2. The observed
distribution is bimodal: a 2-component mixture beats 1 by BIC, with components at 0.17 and
0.03, and the antimode is 0.124. With N2 that break sits within 0.01 of the error-rate cutoff,
so on the easy null the "break" and the "error rate" agree.

| Variant, q = 0.10 | Cutoff | Pairs kept | Kept / true (weak labels) | Precision | Recall | Realized error [95% CI] |
|---|---|---|---|---|---|---|
| N2, raw r | r ≥ 0.114 | 24.8% | 19 / 13 | 0.68 | 0.81 | **0.32** [0.13, 0.57] |
| N2, per-company z | z ≥ 2.10 | 29.4% | 20 / 14 | 0.70 | 0.88 | **0.30** [0.12, 0.54] |
| N3, raw r | r ≥ 0.171 | 13.9% | 10 / 10 | 1.00 | 0.63 | 0 [0, 0.31] |
| **N3, per-company z** | **z ≥ 4.12** | **13.1%** | 10 / 9 | **0.90** | **0.56** | **0.10** [0, 0.45] |

For comparison, with no cut the candidate pairs have precision 0.13.

What the test settles and what it does not:

1. **The peer null is miscalibrated.** Its cutoff promised 10% error and delivered about 30%,
   with a CI that excludes 0.10. An unnamed-company null is too easy. It cannot set the cutoff.
2. **The passing-mention null is consistent with its target, not yet shown to meet it.**
   0 of 16 labelled true pairs fell inside N3, which supports the assumption at n = 16 but
   cannot rule out up to about 20% contamination. Realized error ~0.10 has a CI of 0 to 0.45.
   Carry N3-z forward. The real labelled sample decides whether it holds.
3. **Recall problem for the largest companies.** Every N3 variant keeps 0 to 15% of pairs for
   Google, Meta, Apple, Microsoft and Nvidia, against ~16% for the rest. Aggregator pages are
   kept at 4 to 8%. Part of this is correct, since mega-caps are named in passing constantly.
   Part may be the description problem: a generic "technology company" description scores
   flat against everything. This is the first thing the audit of the cut must break down by
   company on the real sample, and the description comparison (2.5) is the lever.
4. **The weak-label sample is not representative.** It over-samples aggregators (62% vs 41%)
   and has no non-English articles. That is the failure the representativeness check exists to
   catch. The real labelled sample is stratified to avoid it (3.2).

All of these numbers are on BGE-large. Null and observed distributions are model-specific,
so the cutoff is re-derived on the chosen model's scores (2.11, Part 7).

### 2.11 Model choice: from published benchmarks, run on Bouchet

**Decision (yours, 2026-11-03).** No model weights are downloaded onto the local machine for
benchmarking. The full run uses the newest strong open embedding model, run on Bouchet, chosen
from published benchmark results. Nothing is embedded twice: the model is fixed before the full
run.

**Local evidence that stands.** All local tests used BAAI/bge-large-en-v1.5, already on this
machine: the contract test (1.3), the article test (2.4) and the null cutoff (2.10). They show
the *design* works or fails. They do not rank models. The cutoff in 2.10 is re-derived from
the null on the chosen model's scores at the start of the Bouchet run, because null and
observed distributions are model-specific.

**Invariant.** E5-large stays the Part II *analysis* model and is not a candidate for matching
(CLAUDE.md: the two embedding passes stay separate).

**Chosen model and the published numbers behind it.**

**Chosen: `microsoft/harrier-oss-v1-0.6b`.** **Fallback: `Qwen/Qwen3-Embedding-4B`.**

Scores below are from model cards and the Microsoft/Bing release blog. The MTEB leaderboard page
is dynamic and could not be read directly.

| Model | Params | Released | Dim | Max tokens | License | MTEB (Multilingual, v2) mean | MTEB (eng, v2) mean | Status of the number |
|---|---|---|---|---|---|---|---|---|
| **harrier-oss-v1-0.6b** | 0.6B | Apr 2026 (repo 2026-03-30) | 1024 | 32,768 | MIT | **69.0** (69.01 "Mean(Task)") | not published | vendor-reported; MTEB results-repo entry exists but was not readable |
| Qwen3-Embedding-0.6B | 0.6B | Jun 2025 | 1024 (MRL 32-1024) | 32K | Apache-2.0 | 64.33 | 70.70 | model card, confirmed |
| **Qwen3-Embedding-4B** | 4B | Jun 2025 | 2560 (MRL) | 32K | Apache-2.0 | **69.45** | 74.60 | model card, confirmed |
| Qwen3-Embedding-8B | 8B | Jun 2025 | 4096 (MRL) | 32K | Apache-2.0 | 70.58 | 75.22 | model card, confirmed |
| harrier-oss-v1-270m | 270M | Apr 2026 | 640 | 32K | MIT | 66.5 | not published | vendor-reported |
| harrier-oss-v1-27b | 27B | Apr 2026 | 5376 | 32K | MIT | 74.3 | not published | vendor-reported |
| llama-embed-nemotron-8b | 7.5B | Oct 2025 | 4096 | 32K | NVIDIA, non-commercial | 69.46 | not published | model card |
| EmbeddingGemma-300m | 300M | Sep 2025 | 768 | 2,048 | Gemma terms | 61.15 | 69.67 | model card |
| BGE-M3 | ~568M | 2024 | 1024 | 8,192 | MIT | 59.56 | not published | via Qwen card |
| bge-large-en-v1.5 / e5-large-v2 (incumbents) | 335M | 2023 | 1024 | 512 | MIT | n/a (English-only) | not retrieved | not applicable |

Qwen3 sub-scores, Multilingual / eng v2:

| Model | Classification | Clustering | Pair classification | Retrieval |
|---|---|---|---|---|
| 0.6B | 66.83 / 85.76 | 52.33 / 54.05 | 80.83 / 84.37 | 64.64 / 61.83 |
| 4B | 72.33 / 89.84 | 57.15 / 57.51 | 85.05 / 87.01 | 69.60 / 68.46 |

Harrier publishes no sub-scores.

Sources:

- https://huggingface.co/microsoft/harrier-oss-v1-0.6b
- https://blogs.bing.com/search/April-2026/Microsoft-Open-Sources-Industry-Leading-Embedding-Model
- https://huggingface.co/Qwen/Qwen3-Embedding-0.6B (and -4B, -8B)
- https://huggingface.co/nvidia/llama-embed-nemotron-8b
- https://huggingface.co/google/embeddinggemma-300m
- https://huggingface.co/BAAI/bge-m3

**Why Harrier-0.6B.**

- Newest of the candidates.
- Highest published multilingual mean at or below 4B parameters: 69.0, against 64.3 for the same-size Qwen3.
- Multilingual (94 languages), which matters with 17.8% of bodies non-English.
- 32K context, MIT license.
- Same compute class as the 0.6B Qwen, since both are Qwen3-architecture 0.6B models.

**Why not the larger ones.**

- Qwen3-8B buys +1.6 points over Harrier-0.6B at roughly 10x the compute.
- Harrier-27B buys +5 at roughly 40x the compute and about 55 GB of fp16 weights.
- Nemotron-8B is non-commercial and 8B.

**Cost at full scale.** All figures are estimates, not measured. 1M articles × 512 tokens ≈ 5.1e8 tokens.

| Model | GPU-hours on one A100-class GPU | fp16 weights |
|---|---|---|
| 0.6B (Harrier or Qwen) | ~3-5 | ~1.5 GB |
| Qwen3-4B | ~20-30 | ~9-10 GB |
| Qwen3-8B | ~40-55 | ~17-19 GB |

Storage at 1M × 1024 dims × fp16 is ~2 GB. All three sizes are feasible on Bouchet, so cost
does not rule out the larger models. Quality per GPU-hour does.

**What the choice rests on, and the guard.** Harrier's 69.0 is Microsoft's own number. Before
the full run:

1. Read the MTEB results-repo JSON for harrier-oss-v1-0.6b from the web. That is a file read,
   not a download of weights. Confirm the multilingual mean.
2. Use Harrier's required query instruction on articles. Company descriptions are documents,
   with no instruction.
3. Run the 2.10 null cutoff and the labelled-sample verification on Harrier's scores.

If step 1 fails to confirm the number, or step 3 shows realized precision clearly below what
BGE achieved locally on the same labels, switch to Qwen3-Embedding-4B (69.45, confirmed on its
card) before the full run. That is the only case where anything is embedded twice, and then only
the labelled slice.

**Bouchet run cost.** UNVERIFIED (Bouchet) until measured. The first job embeds a 2,000-article
slice, logs articles/second and GPU memory, and projects the full run before the full run is
submitted.

---

## Part 3. Measurement: what accuracy we can claim at each stage

### 3.1 Claim table

| Stage | What we can claim | What we cannot claim |
|---|---|---|
| GKG extraction (does the org string refer to a real mention of the company?) | precision of the **pull**, measured on the hand-labelled sample (3.2), by stratum. Preliminary, unvalidated: **~35%** of candidates are primarily about the tagged company (40-article model read, 2.4) | anything about GKG's recall: articles GKG never tagged are invisible to us. There is no published precision for GKG org extraction. Our number is the only one. |
| SQL candidate filter | recall relative to the GKG pull (via `AllNames` check, 2.2) | recall relative to all news |
| Body fetch | measured yield and bias by source bucket | that fetched articles are representative of blocked ones |
| Embedding matcher | precision/recall/F1 with 95% CIs on the labelled sample, separately for `full_text` and `title_only` | accuracy outside the labelled strata, beyond the automated-check agreement in 3.3 |
| Contract → company | disagreement rate between slug token and embedding; precision on a hand audit of all disagreements plus a random 200 | nothing more is needed: the event table is small enough to audit the uncertain rows completely |

### 3.2 Hand-labelled stratified sample (grades the full-text matcher)

- **Population:** candidate articles from 2.1 on panel company-days, with fetched bodies.
- **Strata:** company tier (mega / large / mid / thin, 4) × GKG prominence (mentions 1 / 2 / ≥3
  crossed with first mention early/late, 4 buckets) × source bucket (primary / aggregator /
  long-tail, 3). Draw ~25 per cell over non-empty cells: **~800–1,000 articles**. Oversample
  the peer pairs (Google/Microsoft/Meta, the banks, Coinbase/Robinhood) and two-company stories.
- **Label per (article, company) pair:** `primary_subject` / `substantive_secondary` /
  `passing_mention` / `not_the_company`. "Firm news" for the thesis = the first two. This
  mirrors the RavenPack relevance idea with an explicit rubric.
- **Protocol:** written rubric first; label blind to the matcher's score; you (or a second
  labeller) relabel a random 15% after a gap for agreement (Cohen's κ). Reweight by stratum
  sizes to get population estimates; bootstrap CIs.
- **Output:** precision and recall of (a) the raw GKG pull, (b) the SQL filter, (c) the
  embedding matcher at the chosen probability cut, each with CIs. Item (a) answers your first
  challenge directly.

Labelling time at ~45 seconds per article with the body visible: ~10–12 hours for 900. A small
labelling page (one article, the candidate company, four buttons) cuts that. It is the one
build item in this plan worth doing before anything else.

### 3.3 Automated check on a large sample

On a random ~20k of the fetched candidates (1 hour of fetching, 2.3):

- Run an LLM judge with the same four-way rubric on headline + first ~600 words.
- **Calibrate it** against the hand labels first: report its agreement with the hand labels
  (accuracy, κ). Only if that clears ~0.85 does the judge become the large-sample referee.
- Report embedding-matcher vs judge agreement on the 20k, by stratum. Disagreements are
  where the matcher's errors concentrate; sample 100 of them back into hand labelling.
- Cost: priced at run time against the current model rate card. Tokens are ~1k per article,
  ~20M total. A local open-weight model (`config/openweight_llm.yaml.template`) is the zero-cost
  alternative if calibration passes.

### 3.4 Coverage on the full candidate set

For all ~4.5M whole-token candidates (or the tier fetched), report:

- share with a fetched body
- share assigned to ≥1 company
- share with two companies
- **company-days with ≥1 assigned article**, out of 9,548, per company

The last number determines whether thin companies (Databricks, Workday, Datadog) have any
usable shocks at all.

---

## Part 4. Answers to your three challenges

**1. "Nobody knows the accuracy of the underlying pull."** Correct, and I could not find any
published precision for GKG org extraction. The plan measures it: the hand-labelled sample
labels every (article, company) pair the GKG pull produced, so precision of the pull itself is
a direct output (3.2a), stratified by prominence and source. The large-sample check (3.3) uses
the bodies we fetch anyway, calibrated to the hand labels before it is trusted. The claim table
(3.1) says what is and is not claimable per stage. What the local data already shows without
labels: 16% of matches come only from person names and 4% only from substrings inside other
words, and 11.8% of rows touch more than one company and were assigned to the first (F§5b).

**2. "Co-occurrence needs per-company catalogs."** Agreed, and dropped. Section 2.6 weighs it
against the body-text method and rejects it on exactly that ground. The replacement needs one
description per company and nothing else. Its price is fetching, measured in 2.3. The
measured async rate (11.4/s locally) makes the 191k tier an overnight job instead of the
65-hour estimate that kept the pipeline from doing it.

**3. "The series names don't cover the other types."** Enumerated (F§4). Series cover the
price, earnings, KPI, valuation and IPO-market-cap families. **The series method misses 485
universe markets (7.0%) and 298 of 628 groups (47%)**: early-era earnings, CEO changes, M&A,
IPO timing, one-off KPI ladders (bank Q2 metrics, Oracle RPO, Micron DRAM, Nike segments),
SpaceX valuation and market-cap ladders, and the April/May 2026 HOOD/COIN/AAPL/META hit ladders.
What catches them is the **event**: every one of them has an `events[0]` with a title, which goes
through the event route in 1.3 (token first, then embedding, then hand review) and the one-time type labelling (1.4 option A).
Coverage by type is in F§4a–4c. The enumeration also found whole price families the universe never
had: 2,440 closing-bucket and 674 up/down markets.

**4. "Is the series mapping complete against the local universe?"** No.

| Universe family | Contracts | Covered by series | Missed by series | What catches the missed ones |
|---|---|---|---|---|
| price_ladder | 6,174 | 6,057 | 117: April/May 2026 HOOD/COIN/AAPL/META hit ladders (60) + 57 misfiled KPI rows | event title/slug token; type from hand labels |
| corporate_event | 470 | 203 (earnings series) | **267**: early earnings, CEO, M&A, IPO dates, mentions | event route: slug/name token (74% of series-less events), else embedding δ ≥ 0.02, else hand review |
| revenue_ladder | 170 | 95 (`*-kpis`) | 75: one-off KPI ladders (bank Q2, Oracle, Micron, Nike, Dell...) | same event route; type hand-labelled once |
| valuation_ladder | 110 | 88 | 22: SpaceX valuation, Reddit IPO buckets | same |
| market_cap_ladder | 4 | 0 | 4: GME, Nvidia 2024 | same |
| **Total** | **6,928** | **6,443 (93.0%)** | **485 (7.0%)** | |
| Groups (628) | | 323 fully, 7 partly | **298 (47%)** with no series | same |

The 7% looks small, but it is half the groups and 57% of the corporate events, which are the
contracts most directly about discrete news. In the other direction, the series method also
finds contracts the universe never had: 2,440 closing buckets, 674 up/down binaries and 347
lower barriers.

---

## Part 5. Sequencing

| # | Step | Where | Depends on | Output |
|---|---|---|---|---|
| 1 | Company registry: `company_id`, names, ticker, Wikipedia title, CIK; build both description sets | local | — | `config/companies.yaml`, `data/companies/descriptions_{wiki,10k}.parquet` |
| 2 | Contract event table from cached Gamma: series route + series-less route, slug token, type, strike, expiry. Embedding for token-less series-less events comes from B4 | local (read/write) + Bouchet (B4) | 1 | `contract_events.parquet` + disagreement report |
| 3 | Hand-audit contract disagreements + label the ~770 series-less events | local (you) | 2 | audited labels; reconciliation vs universe (1.7) |
| 4 | Panel key set (company-days) from bars | local | 3 (scope decisions change the panel) | `company_days.parquet` |
| 5 | GKG schema check (free), day-keyed SQL, dry-run cost | local w/ GCP creds | 4 | query + cost |
| 6 | Pull candidates; fetch labelled-sample bodies (~1k) + check sample (~20k) | local | 5 | candidates + bodies |
| 7 | Labelling page + hand labels (~900) | local (you) | 6 | gold labels |
| 8 | Cutoff from the null on the chosen model (2.10); labelled-sample verification; both description sets; title-only arm | Bouchet (B1, B2, B3, B5) + local stats on score files | 7 | cutoff, verification table with CIs |
| 9 | LLM-judge calibration + 20k agreement | API (no local compute) or Bouchet (B7, open-weight) | 7, 8 | automated-check report |
| 10 | Scale fetch to the chosen tier; full-corpus assignment; coverage report | Bouchet (B6, B8) | 8 | matched corpus + coverage |

Local work is reading and writing only (standing rule, 2026-11-03): no model downloads, no embedding runs, no benchmarks on the Mac. Every compute step is in Part 7.

## Part 6. Decisions I need from you

1. Scope: add closing buckets, up/down and "dip to" lower barriers (recommended)? Product/ops events in or out?
2. Series-less type labelling: option A (hand-label ~770 once, recommended) or B (prototype embeddings)?
3. Labelled sample size and who is the second labeller for the κ check.
4. Fetch tier for the full run: 191k top-per-company-day (recommended start) or the 1M strong tier.
5. Target error rate q for the null-based cutoff (2.10). Proposed q = 0.10, meaning 1 in 10 assigned pairs may be wrong.
6. Body retention: the middle option in 2.7 (keep matched + audit samples + 2% reservoir), or fetch-embed-discard for everything.
7. Non-English articles (17.8%): multilingual model, or drop.

*Housekeeping:* the Wikipedia test fetch sent the user's email in its User-Agent header. The
build should use a project contact string instead. Scratch scripts for every number here are in
the session scratchpad and are not committed. They can be moved to `scripts/audit/` on request.

## Part 7. Tests waiting on Bouchet

Standing rule from 2026-11-03: nothing heavy runs locally. Each test below needs GPU compute,
model weights, or bulk network work, and you run it on Bouchet. Inputs are files the local
read/write steps produce. Outputs come back as small score or log files, and the analysis of
those files is local.

Order matters. B0 to B3 decide the model and the cutoff, and nothing downstream should run
before they do.

| # | Test | Needs | Decides | Blocks |
|---|---|---|---|---|
| **B0** | Bouchet facts check (F§7): diff `universe.parquet` and bars against local; GDELT corpus row count (546,657 vs 546,543 local); list `data/news/bodies/`; confirm outbound HTTP from a compute node (fetch 20 URLs) | shell on Bouchet, 10 min | whether local and Bouchet data are the same; whether fetching can run there | B6 |
| **B1** | Embed the labelled slice with **harrier-oss-v1-0.6b**: ~1k labelled article bodies (with the required query instruction) + 94 Wikipedia descriptions | one GPU, harrier weights (~1.2 GB), bodies from step 6, `wiki_desc.json` | confirms or rejects the model choice (2.11): realized precision at the null cutoff vs BGE's local result on the same labels | B2, B3, B5, B8 |
| **B1-fallback** | Same slice with **Qwen3-Embedding-4B**, only if B1 fails or the MTEB results-repo check (2.11) does not confirm 69.0 | one GPU, ~9 GB weights | the fallback model | same |
| **B2** | Null cutoff on the chosen model: N1/N3 nulls, per-company z, t* at q = 0.05 / 0.10 / 0.20; audit of the cut by company, month, source, language, score band; representativeness of the labelled sample (2.10) | B1 score matrix (articles × 94); analysis is light and can run locally on the returned file | the production cutoff, and whether N3's "passing = non-match" assumption holds on real labels | B8 |
| **B3** | Description source comparison: embed 10-K Item 1 / 20-F descriptions for public companies; rerun B2 with each set and the average (2.5) | GPU minutes; EDGAR text pulled by a read/write step | Wikipedia vs filings vs average; whether filings fix the mega-cap recall problem (2.10 result 3) | B8 |
| **B4** | Contract events with the chosen model: 2,854 event texts against 94 descriptions; margin table vs slug (1.3) | GPU minutes; `emb_events` text column | the embedding assignment for the ~26% of series-less events with no slug token; size of the hand-review queue | step 3 |
| **B5** | Non-English arm: score non-English labelled articles with the chosen (multilingual) model; compare realized precision to English | from B1, no extra run if the slice includes them | route vs drop for the 17.8% non-English (Part 6, item 7) | B8 |
| **B6** | Body-fetch throughput from Bouchet: 2,000 URLs from the candidate set, same settings as the local probe (2.3) | outbound HTTP (from B0) | where the full fetch runs, and the real rate at the chosen tier | B8 |
| **B7** | LLM judge (3.3), only if run on an open-weight model rather than the API: 20k articles, four-way rubric; calibrate against hand labels first | one GPU, open-weight LLM | whether the automated check is trustworthy enough to referee the 20k sample | — |
| **B8** | Full run at the chosen tier (191k recommended): fetch → embed (chosen model) → score candidates → apply B2 cutoff → keep bodies per 2.7; first job embeds a 2,000-article slice and logs articles/s and GPU memory before the full job is submitted | GPU-hours: ~1 for 191k, ~3-5 for 1M at 0.6B (estimates, 2.11) | the matched corpus, and coverage per company-day (3.4) | Part II |

**What each one returns.** B1 to B5 return score matrices (`.npy`, articles × companies) plus id
lists, a few MB each. B6 returns a fetch log. B8 returns the matched-pair table, embeddings
and retained bodies, which stay on Bouchet.

**Not on this list.**

- The BigQuery pull (step 5). It is cloud compute billed to the GCP project, run from
  wherever the credentials are. The dry-run and budget gate apply.
- Fetching the ~1k labelled-sample bodies (step 6). That is light network I/O, not compute.
  It can also go on B6 if you prefer no fetching from the Mac at all.
