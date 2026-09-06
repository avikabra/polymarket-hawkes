# GDELT Coverage Audit — Company-Contract Universe

*Weeks 7-9 · run 2026-09-05 · script `scripts/audit_gdelt_company_coverage.py`*

Answers the data-review question **"do we have news coverage for these contracts, and is it usable?"**
Window 2024-01-01 → 2026-08-29. Entity regex over `V2Organizations` + `V2Persons` for the 90
companies in `COMPANY_DICT` that survive an ambiguity filter.

**Headline: GDELT gives us volume but not quality. It is adequate as a match-scoring
substrate and inadequate as the article corpus. The audit produces a concrete, evidence-backed
case for a licensed newswire.**

---

## 0. Cost finding (fix before anyone runs script 04 again)

`src/news/gdelt/bigquery.py` queries `gdelt-bq.gdeltv2.gkg`. That table's `DATE` column is
`INT64`, so `WHERE DATE >= …` **cannot prune partitions** — every query scans the full column set.

| query shape | scanned | cost |
|---|---|---|
| `gkg`, 10 cols, **one day** of window | 3.40 TB | ~$21.26 |
| `gkg_partitioned`, 7 cols, **32 months** | 0.435 TB | ~$2.72 |
| `gkg_partitioned`, 4 cols, **32 months** | 0.064 TB | ~$0.40 |

Script 04 over a 2024→2026 window would cost **five figures**. The partitioned twin
`gdelt-bq.gdeltv2.gkg_partitioned` (prunes on `_PARTITIONTIME`) answers the same questions for
about a dollar. The whole audit below cost **$1.04**.

> **Action:** point `GDELTClient._TABLE` at `gkg_partitioned` and filter on `_PARTITIONTIME`
> before script 04 is next run. Not yet done — script 04 is still sports-scoped and out of the
> overnight scope.

---

## 1. Volume — abundant in aggregate

- **20,499,205** matched GKG records over 32 months
- **88 of 90** companies have non-zero coverage; **0** universe companies have none
- all 32 months represented

Per-company monthly medians (distinct URLs), for companies in the current universe:

| tier | companies | median URLs/month |
|---|---|---|
| mega-cap | Meta, Google, Netflix, Microsoft, Nvidia | 18k – 125k |
| large-cap | Walmart, Apple, Amazon, Tesla, Pfizer | 4k – 10k |
| mid | AMD, Micron, Merck, OpenAI, Stripe, Intuit, Salesforce, Palantir | 270 – 900 |
| **thin** | **Airbnb, CrowdStrike, Zoom, Home Depot, Anthropic, Coinbase** | **130 – 200** |
| **very thin** | **Robinhood (58), Workday (58), Cloudflare (40), Datadog (24), Databricks (18)** | **< 60** |

Coverage floor across the 29 universe companies × 32 months:

| floor | share of company-months clearing it | companies clearing it every month |
|---|---|---|
| ≥ 30 URLs | 92.6% | 24 / 29 |
| ≥ 100 URLs | 80.9% | 18 / 29 |
| ≥ 300 URLs | 56.7% | 12 / 29 |
| ≥ 1000 URLs | 39.9% | 10 / 29 |

**Data gap:** June 2025 has only **14 days** of GDELT data (4.68M rows vs a ~10M/month norm);
July 2025 is missing one day. Any event study must treat 2025-06 as a hole, not as low news volume.

---

## 2. The structural tension (most important finding)

The companies with the **richest ladder structure** have the **thinnest news coverage**.
Cross-referencing `contract_groups.parquet` against coverage:

| group | members | strike metric | median URLs/month | min month |
|---|---|---|---|---|
| Databricks | **12** | valuation | **18** | **7** |
| Anthropic | 10 | valuation | 134 | 43 |
| OpenAI | 10 | valuation | 400 | 179 |
| Stripe | 10 | valuation | 315 | 118 |
| Robinhood | 14 | price | 58 | 17 |
| Coinbase | 14 | price | 150 | 52 |
| Google / Meta / Netflix | 14 | price | 39k – 125k | 16k+ |

Thread 2 (the latent-factor strike-ladder model) needs **many strikes per company-month** — which
points at the private-company valuation ladders. Thread 1 (article↔contract matching) needs **many
articles per company** — which points at the mega-caps. **These are disjoint sets.**

This is a real design constraint, not a data-cleaning problem, and it is the single most important
thing to raise. Options are laid out in §6; I have deliberately not picked one.

---

## 3. Quality — the corpus is mostly not journalism

Source composition within the top-400 domains (a *lower* bound on the junk share, since the
long tail is worse):

| bucket | share of records | example domains |
|---|---|---|
| "other" (regional/foreign/long-tail) | 65.8% | indiatimes, 163.com, sina.com.cn, setn.com, ltn.com.tw |
| aggregator | 16.7% | yahoo, iheart, biztoc, marketscreener, insidermonkey |
| **content farm** | **15.0%** | themarketsdaily, dailypolitical, tickerreport, wkrb13, modernreaders |
| **primary journalism** | **2.5%** | forbes, cnbc, businessinsider, guardian, bbc, theverge, bloomberg |

The content-farm bucket is the MarketBeat syndication network — auto-generated
"shares crossed above their 200-day moving average" filler, published on a schedule and
uncorrelated with genuine information arrival. It is **6× more prevalent than primary journalism**.

**The newswires are effectively absent.** Checked by name against the top-400 domains:

| outlet | rank | records | share |
|---|---|---|---|
| Bloomberg | 362 | 6,150 | 0.083% |
| Reuters | **not in top 400** | < 5,766 | < 0.08% |
| AP, WSJ, FT, NYT, Barron's, Economist | **not in top 400** | < 5,766 each | < 0.08% each |

The top-400 cutoff is 5,766 records — i.e. Reuters published fewer than ~180 GDELT-indexed items
*per month across all 90 companies combined*. For a study whose whole premise is measuring
reactions to company news, the wire services that actually move markets are missing from the
corpus almost entirely.

---

## 4. Entity matching is unreliable — and this is evidence for Thread 1

Naive substring entity matching, which is what the current pipeline would do, fails badly.

**Meta: only 5.0% of matched `meta*` organisation tokens are Meta Platforms.** The rest:

```
rheinmetall (690)          sunrise energy metals (232)   metaoptics ltd (220)
metals ltd (224)           apex critical metals (150)    korean metal worker union (111)
nord precious metals (134) metal church (90)             russian union suppliers metal (75)
```

Meta's 4.08M records — **20% of the entire matched corpus** — are dominated by metallurgy,
mining, and the "Facebook" alias firing on share-this-article boilerplate. Netflix matches 6.7%
of *all* sampled rows, mostly entertainment listicles rather than company news. Ford matches 4.0%.

Twelve aliases (`ARM`, `Block`, `Square`, `Shell`, `Visa`, `Intel`, `Lucid`, `AMC`, `Coke`,
`Citi`, `Amex`) had to be dropped from the regex outright because they are unusable as
entity strings.

> **Methodological read:** this is direct empirical support for the DUS novelty argument.
> Article→contract matching cannot be a similarity lookup or a string match — the naive baseline
> is ~5% precision on a major name. It has to be a *learned, validated* structure, which is
> exactly [[novelty-thread-matching]] / Thread 1 in `reports/advisor_update_math.md`. The
> liquidity/abnormal-reaction moment condition is what makes that claim testable rather than
> asserted.

---

## 5. Timestamps and metadata

**Timestamps (confirmed, not assumed).** In the 442,257-row August 2026 sample:
`DATE` takes exactly **4 distinct minute values** (00/15/30/45) and **1 distinct second value**.
It is the GDELT crawl/ingest slot on a 15-minute grid, **not** publication time.

> The project invariant `timestamp_precision = "day"` for GDELT is **correct and should stay**.
> A 15-minute grid looks precise but carries unknown crawl lag, so it cannot support the
> intraday reaction windows the thesis needs. This is the strongest single technical argument
> for a publisher feed with real `pubDate`.

**Metadata richness** (same sample) is genuinely good:

| field | non-empty | mean items/record |
|---|---|---|
| V2Tone | 100.0% | 1 |
| V2Organizations | 96.2% | 8.2 |
| V2Themes | 88.2% | 60.1 |
| V2Locations | 80.6% | 14.1 |
| V2Persons | 75.0% | 8.0 |

Themes/tone/entities are dense enough to be useful **features and match-side signals** — which
supports keeping GDELT as a matching substrate even if the article text comes from elsewhere.

---

## 6. Body text — retrievable, but biased toward the junk

Live stratified probe, 160 URLs, 40 per bucket (`scratch/test_body_fetch_rate.py`,
saved to `data/news/audit/body_fetch_probe.parquet`):

| bucket | n | success | median chars | ≥800 chars |
|---|---|---|---|---|
| aggregator | 40 | **100%** | 2,457 | 100% |
| content_farm | 40 | **100%** | 5,171 | 95% |
| other | 40 | 97% | 2,812 | 93% |
| **primary_journalism** | 40 | **72%** | 3,681 | 70% |
| **overall** | 160 | **92.5%** | — | **89.4%** |

Headline 92.5% looks healthy, but the ordering is backwards: **the sources we most want fail
most often** (paywalls, bot-blocking), and the sources we least want extract perfectly. Naive
corpus-building therefore actively *concentrates* the junk.

**Throughput ceiling.** The historical script-06 run sustained ~110 URLs/min. At that rate the
20.5M-record corpus is ~130 days of fetching. Even 1% is ~30 hours. Body-fetching at corpus
scale is not on the table; the corpus must be narrowed by matching *first*.

---

## 7. Verdict, and what it means

| axis | verdict |
|---|---|
| volume | **PASS** — abundant for mega/large-cap, marginal below ~200 URLs/month |
| company coverage | **PASS** — 0 universe companies with no coverage |
| timestamps | **FAIL for intraday** — 15-min crawl grid, not publication time |
| metadata | **PASS** — dense themes/tone/entities, good match-side features |
| source quality | **FAIL** — 2.5% primary journalism, 15% content farm |
| entity precision | **FAIL naive** — 5% precision on Meta; needs a learned matcher |
| body text | **CONDITIONAL** — 92.5% overall but 72% on the sources that matter |

**GDELT stays** as (a) the discovery/candidate-generation layer and (b) a metadata feature source.
**GDELT cannot be** the timestamped article corpus for an intraday event study. That gap is what
the newswire request is for — see `reports/reuters_data_request.md`.

---

## Open decisions (not mine to make)

1. **The §2 tension.** Anchor the study on mega-caps (deep news, shallower ladders), on private
   valuation ladders (deep ladders, sparse news), or run both as separate panels? This shapes
   which of the two novelty threads carries the empirical weight.
2. **Public vs private.** The universe currently includes private companies (Databricks,
   Anthropic, OpenAI, Stripe) via valuation ladders. This diverges from the literal
   "public equities" framing and is still unresolved from the last session.
3. **Content-farm handling.** Drop them, or keep them as a deliberate *placebo* channel —
   scheduled non-news that should produce no abnormal reaction, which is a clean falsification
   test for the Thread 1 moment condition. The second option is more interesting and nearly free.

## Reproduce

```bash
uv run python scripts/audit_gdelt_company_coverage.py   # ~$1.04, ~10 min
uv run python scratch/analyze_gdelt_audit.py            # summary tables
uv run python scratch/check_gdelt_falsepos.py           # entity-precision probe
uv run python scratch/test_body_fetch_rate.py           # live body-fetch probe
```

Outputs in `data/news/audit/`: `gdelt_company_month.parquet`, `gdelt_source_mix.parquet`,
`gdelt_metadata_sample.parquet` (442,257 rows), `body_fetch_probe.parquet`.
