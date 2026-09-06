# Newswire Data Request — Draft

*Weeks 7-9 · drafted 2026-09-05 · evidence base: `reports/gdelt_coverage_audit.md`*

> **Status: DRAFT for Prof. Kelly's review.** Not sent. Three things need a decision before it
> goes anywhere: the company list (§2, depends on the public-vs-private question), the delivery
> route (§6 — Yale library licence vs. direct academic request), and who signs it.

---

## 1. One-paragraph ask

We need a **timestamped, full-text archive of company news for ~30 named companies over
2024-01-01 → 2026-08-31**, with publication timestamps accurate to the minute. The research
measures how prediction-market prices re-price in the minutes-to-hours after a news item lands,
so *timestamp precision is the binding requirement* — more than volume, more than breadth.

## 2. Companies and window

- **Window:** 2024-01-01 → 2026-08-31 (32 months), matching the Polymarket contract universe.
- **Companies:** the ~30 names with tradeable Polymarket contracts. Current list in
  `data/polymarket/contract_groups.parquet`; as of the August 2026 slice it is
  Airbnb, AMD, Amazon, Anthropic, Apple, Cloudflare, Coinbase, CrowdStrike, Databricks, Datadog,
  Google, Home Depot, Intuit, Merck, Meta, Micron, Microsoft, Netflix, Nvidia, OpenAI, Palantir,
  Pfizer, Robinhood, Salesforce, Stripe, Tesla, Walmart, Workday, Zoom.
- **Open:** four of these (Anthropic, Databricks, OpenAI, Stripe) are **private** companies that
  trade as valuation ladders. They carry our deepest strike structure but the thinnest coverage.
  Whether they stay in decides whether we need a vendor with strong private-market/startup
  reporting. **Flagged for Prof. Kelly.**

## 3. Fields required

| field | why | hard requirement? |
|---|---|---|
| **publication timestamp (UTC, minute-precision)** | defines event time τ; the entire reaction window hangs on it | **yes — deal-breaker** |
| headline + full body text | analysis embeddings (E5-large, 768-dim) | yes |
| unique story ID | dedup, and linking updates to originals | yes |
| company/RIC tagging | ground-truth entity labels — see §5 | strongly preferred |
| story type (alert / article / update / correction) | separates first-print from follow-ups | strongly preferred |
| take/revision sequence | first print is the event; revisions are not | preferred |
| topic/subject codes | match-side features, controls | preferred |
| embargo or wire-release flag | flags pre-scheduled vs. unscheduled news | nice to have |

**First-print timestamps matter more than final-version timestamps.** For an event study the
object of interest is the moment the wire crossed, not when the story was last edited.

## 4. Estimated volume

From GDELT as a lower bound on the same company set:

- all 29 universe companies, 32 months: **10.2M** GDELT records (inflated — see §5)
- excluding the 10 mega-caps: **205,461** distinct URLs over 32 months
- a wire-only corpus should be far smaller: order **10²–10³ stories per company-year**,
  so roughly **50k–150k stories total**

This is a modest archive request, not a firehose. We do not need real-time or streaming access —
a one-time historical extract is sufficient.

## 5. Why GDELT is not sufficient (the evidence)

We audited GDELT over exactly this universe, then ran a direct validation probe
(`reports/gdelt_validation_probe.md`). GDELT + scraping *suffices to bootstrap* the matching
pipeline — so this request is scoped to the **intraday precision study**, which four findings
disqualify GDELT from:

1. **No publication timestamps.** GDELT's `DATE` field takes 4 distinct minute values
   (:00/:15/:30/:45) and 1 second value across a 442,257-row sample — it is the crawler's
   15-minute ingest slot with unknown lag, not publication time. Our own pipeline already flags
   GDELT as day-precision for this reason. Day precision cannot support an intraday study.
2. **The wires are absent.** Reuters, AP, WSJ, FT, NYT, Barron's and the Economist are *all*
   outside the top-400 domains for our companies; each published fewer than ~180 GDELT-indexed
   items per month across all 90 companies combined. Bloomberg ranks 362nd at 0.083%.
3. **The corpus is mostly not journalism.** 15.0% of records come from the MarketBeat
   content-farm network (auto-generated "crossed above its 200-day moving average" filler),
   16.7% from aggregators, and only **2.5% from primary journalism**.
4. **Entity tags are unreliable.** Only **5.0%** of organisation tokens matching `meta*` refer to
   Meta Platforms — the rest are Rheinmetall, precious-metals miners, and metallurgical unions.
   Twelve company aliases had to be dropped as unusable. Vendor-supplied RIC/company tagging
   removes an entire error channel.

And a practical constraint: body-text retrieval from open URLs succeeds 92.5% overall but only
**72% on primary-journalism sources** (paywalls, bot-blocking), so scraping systematically
*enriches for the junk*. At ~110 URLs/min sustained throughput, corpus-scale scraping is
infeasible regardless.

**Direct validation (2026-09-06 probe, 40 real corporate events, \$0.05).** Confirmed on this exact
use case: only **77.5%** of events had any GDELT hit within ±2 days; **1.2%** of matched URLs were
primary journalism; body-text scraping of those primary URLs succeeded **69%** of the time; and —
decisively — the market resolves at a **~24-minute** median inter-trade gap around events, so
GDELT's day-precision timestamps are **~60× too coarse** to align cause and effect. Minute-precision,
paywalled, entity-tagged wire text is exactly what closes these gaps.

**What GDELT is still good for**, and what we will keep using it for: candidate generation, and
dense metadata features (V2Themes 88% non-empty at ~60 items/record, V2Tone 100%,
V2Organizations 96%). The request is to *replace the article corpus*, not the whole pipeline.

## 6. Delivery, licensing, terms

- **Format:** JSON or JSONL, one object per story, delivered as a bulk historical extract
  (S3/GCS drop or physical transfer both fine). No streaming/real-time needed.
- **Use:** non-commercial academic research — a senior thesis at Yale under Prof. Bryan Kelly.
  Outputs are aggregate statistics and model coefficients; **no article text is republished**.
- **Storage:** access-controlled institutional storage, deleted at project end if required.
- **Attribution/citation:** as the licence requires.
- **Route — open question.** Check the **Yale library's existing entitlements first**
  (Refinitiv/LSEG, Factiva, Bloomberg, RavenPack are all commonly licensed) before making a
  direct vendor request. An existing institutional licence is faster and free; a direct academic
  request is the fallback. This depends on the Yale cluster/data-access action item.

## 7. Fallback vendors, in priority order

| option | timestamps | wire coverage | private-co coverage | route |
|---|---|---|---|---|
| **LSEG/Refinitiv News Archive** | first-print, ms | excellent | moderate | Yale licence likely |
| **Dow Jones / Factiva** | minute | excellent (WSJ+DJ wire) | moderate | Yale licence likely |
| **RavenPack** | ms, pre-tagged entities + novelty scores | excellent | moderate | academic programme |
| **Bloomberg (via terminal entitlement)** | ms | excellent | good | export limits are the problem |
| **AP Developer / academic** | minute | good | weak | direct request |
| **Publisher APIs (NYT, Guardian)** | minute | partial | weak | free, but narrow |

RavenPack deserves a look: it ships entity tagging *and* a novelty/relevance score, which would
give Thread 1's learned matcher a genuine external benchmark to beat rather than only a
cosine-similarity null.

---

## Before this is sent — decisions needed

1. **Public vs. private companies** (§2) — unresolved from the previous session; it changes the
   vendor shortlist.
2. **Route** (§6) — Yale library entitlement check must happen first; it may make the request moot.
3. **Whether a licence permits what we need.** Most academic news licences forbid redistribution
   but permit derived quantitative outputs. Our outputs are embeddings and regression
   coefficients — almost certainly fine, but worth confirming explicitly rather than assuming.
