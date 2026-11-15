# Data-Review Deck — Weeks 7-9 (DRAFT)

*For Prof. Bryan Kelly's late-September data review · drafted 2026-09-05 (overnight run)*
*Answers the three questions from the 2026-08-28 meeting. Draft — one section (Q2 visuals) fills in as the live trade pull completes.*

---

## Q1 — What is the usable market sample?

**A clean, company-only universe of 6,928 contracts across 86 companies and 628 ladder groups, spanning 2024-04-30 → 2026-08-27**, built by day-sliced Gamma enumeration + a company classifier (`company_filter.py`) that keeps individual-company price/valuation/revenue/market-cap ladders and one-off corporate events, and rejects sports, politics, macro, crypto-token, index, and AI-model-leadership markets.

**Contract families** (`contract_groups.parquet` sidecar carries the parent/child ladder structure):

| family | contracts | what it is |
|---|---|---|
| price_ladder | 6,174 | monthly stock-price strikes ("NVDA ≥ \$180 end of July") — the strike ladders for Thread 2 |
| corporate_event | 470 | one-off M&A / earnings / exec / IPO events |
| revenue_ladder | 170 | revenue-threshold ladders (e.g. Nvidia data-center revenue) |
| valuation_ladder | 110 | private-company valuation ladders (OpenAI, Anthropic, Databricks, Stripe) |
| market_cap_ladder | 4 | market-cap threshold ladders |

**Concentration by company** (top 10 by contract count): Apple 715, Google 684, Tesla 683, Microsoft 665, Amazon 660, Meta 656, Nvidia 616, Netflix 551, Palantir 544, Airbnb 189.

**Liquidity (discovery-level screen, from Gamma `volumeNum` — no trades needed):** total lifetime volume **\$79.1M**.

| volume floor | contracts | share |
|---|---|---|
| > \$0 | 6,486 | 93.6% |
| > \$1,000 | 4,875 | 70.4% |
| > \$5,000 | 2,559 | 36.9% |
| > \$10,000 | 1,452 | 21.0% |
| > \$50,000 | 243 | 3.5% |

The top 500 markets hold **62.6%** of all volume — liquidity is concentrated, as expected. **The final liquidity threshold is deliberately left open until the log-odds EDA (Q2) shows whether thin markets manufacture zero-moves.** A trade-level screen (active trading days, trade count, pre/post-event coverage) is being computed on the live pull.

**Honest caveats:**
- **Offset-ceiling risk:** high-volume 2026 days hit Gamma's ~2,100-item page ceiling; company contracts sorting past that on those days *could* be undercounted. Impact looks small (the ceiling is dominated by excluded sports markets) but is not yet verified.
- **Private companies (OpenAI, Anthropic, Databricks, Stripe)** enter via valuation ladders — they carry the deepest ladder structure but the thinnest news (see Q3). Whether to keep them is a scope decision (below).

**Conviction the sample is usable: 8/10.** It's clean, classified, liquidity-characterised, and carries the ladder structure both novelty threads need.

---

## Q2 — What does a real Polymarket reaction look like?

The trade source the pipeline was built on (Goldsky subgraph) was **deprecated** mid-project; trades now come from the **official Polymarket Data-API `/trades`** (verified complete — `sum(size)` reconciles to the penny against Gamma's `total_volume_usdc`; details in `reports/trade_source_decision.md`). **594,984 real trades pulled across all 6,486 traded markets**, resampled to 1-minute log-odds bars. The five visuals (`reports/figures/*_company.png`) were computed on the **liquid subset** (volume > \$10k = 1,452 markets, **72.5M 1-minute bars**); the full universe's liquidity is characterised in Q1.

**The headline: a real reaction is mostly *nothing*, punctuated by *large* jumps.**

- **6-hour log-odds change distribution** (`fig1`, n = 72.0M): a huge spike at exactly zero, mean ≈ 0, **std = 0.44**, with fat symmetric tails.
- **Zero-move share** (`fig2`): **74.6% of 6-hour windows have |Δ| < 0.01 log-odds — even in these liquid markets.** Per-contract median zero-share = 64.8%. This *confirms your concern directly*: inactivity (LOCF between sparse trades) manufactures zeros, so a naive last-trade 6-hour Δ is ~75% structural zeros.
- **But when they move, they move big:** among non-zero 6h windows, median |Δ| = **0.41 log-odds**, 90th pct = 1.66, 99th pct = 5.17. The signal is real and sizeable — it's just *sparse*.
- **Trade frequency / liquidity screen** (`fig3`, `data/polymarket/liquidity_screen.parquet`): per-contract median **154 trades** over **14 active trading days**. Screen pass-rates on the liquid subset: ≥200 trades 40%, ≥10 active days 58%, and **both (≥200 trades & ≥10 active days) = 473 contracts (32.6%)** — a defensible "clean" modelling set.
- **Demean + normalize** (`fig4`) cleans cross-contract level differences as expected; **event-time** (`fig5`) is machinery-only (synthetic events — real ones need the matching pipeline).

**What this means for the target (options, not a decision — that's yours):**
1. **Shorten Δ** (1–2h) — reduces the LOCF dead-zone but not the fundamental sparsity.
2. **Trade-/event-conditioned sampling** — measure Δ only around actual trades or news events, not on a fixed clock grid. Most promising given the 75% structural zeros.
3. **Filter to the clean set** (≥200 trades & ≥10 active days, 473 contracts) before fixing any target.

**Conviction the reaction is usable *with* (2) and/or (3): 7/10.** The reaction clearly exists (large non-zero moves); the work is in not letting inactivity dominate the target. **I have not fixed the target — that's your call.**

---

## Q3 — Can we reliably match full articles to these contracts?

**Audited GDELT coverage over exactly this universe** (`reports/gdelt_coverage_audit.md`, 20.5M records, \$1.04 of BigQuery):

- **Coverage: 94.2% of the 86 universe companies are covered** (81/86). The 5 gaps — AT&T, Block, Coca-Cola, Intel, Visa — are precisely the **ambiguous-ticker names** the audit had to drop; that they're hard to match is *itself* the point (below).
- **But GDELT has three quality gaps as a full-text corpus:** (a) **no publication timestamps** — its `DATE` is a 15-minute crawl grid, not publication time, so it can't support intraday reaction windows; (b) **only 2.5% primary journalism** (15% content-farm, the wires effectively absent — Reuters/AP/WSJ/FT outside the top-400 domains); (c) **entity tags unreliable** — only **5% of `meta*` org-tokens are Meta Platforms**. (The probe below quantifies how far these gaps go — and where GDELT is nonetheless usable.)
- **The 5% Meta precision is the empirical case for the thesis's novelty:** naive string/similarity matching is ~5% precise on a major name, so matching must be a *learned, validated* structure (Thread 1's bilinear metric with liquidity/abnormal-reaction as an out-of-sample validation moment), not a lookup.

**GDELT verification — the "do we already have this?" probe** (`reports/gdelt_validation_probe.md`, cost \$0.051; see `fig6`). I ran 40 real corporate events through GDELT and scraped a bounded URL sample to test whether GDELT + scraping could simply *be* the corpus:

- **Event coverage:** 31/40 events (77.5%) have GDELT hits within ±2 days (9 uncovered).
- **Source quality:** only **1.2% of matched URLs are primary journalism** (90% long-tail "other") — though that is still ~285 primary URLs per event in absolute terms.
- **Full text:** scraping GDELT's primary-journalism URLs yields usable body text **69%** of the time (~31% lost to paywalls — systematically the best sources).
- **Timestamp binding:** the market resolves at a **~24-minute** median inter-trade gap around events, so GDELT's day-precision timestamps are **~60× too coarse** to align cause and effect. *(This corrects an earlier hedge that sparsity made timestamps less important — the probe shows they do bind.)*

**Verdict — GDELT + scraping is a viable *bootstrap*, not a substitute for a newswire:**
- **Use GDELT now** — source-filter to journalism → scrape → a few thousand usable articles: enough to build and validate the matching pipeline (Thread 1) and run a coarse first-cut reaction study, free and immediately.
- **A licensed newswire is justified for the precision pass**, on the two grounds scraping cannot fix — the **24-minute timestamp binding** and the 31% paywall / 22% coverage bias. Draft request: `reports/reuters_data_request.md`.

**Conviction: matching *bootstrap* is workable now 7/10; clean *intraday* matching (needs the newswire) 6/10.**

---

## Decisions (status as of 2026-09-06)

1. **Reaction target — DECIDED: explore all three** (event/trade-conditioned, shortened Δ, clean-set) and compare empirically; the final pick remains yours after seeing the comparison.
2. **Public vs. private — DECIDED: keep both as panels** (public → Thread 1 news; private valuation ladders → Thread 2 structure).
3. **Liquidity cut — DECIDED: vol > \$10k (1,452 contracts)** — matches the bars already built.
4. **Newswire — RESOLVED by the probe:** proceed on GDELT + scraping now; layer a licensed newswire in for the intraday precision pass. Still to choose: route (Yale-library entitlement vs. direct academic request).

## Per-question conviction

| question | conviction | gated on |
|---|---|---|
| Q1 usable sample | 8/10 | — (done; minor ceiling caveat to verify) |
| Q2 real reaction | 7/10 | target choice (yours) — sparsity handled by event/trade-conditioned sampling |
| Q3 matching (bootstrap) | 7/10 | GDELT+scraping viable now (probe-verified) |
| Q3 matching (intraday) | 6/10 | licensed newswire (24-min timestamp binding) + labelled positives |
