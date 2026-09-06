# GDELT-vs-Newswire Validation Probe

*2026-09-06 · answers "do we already have the news corpus in GDELT?" · total cost: \$0.051 BigQuery + 120 scraped URLs · `scratch/probe_gdelt_validation.py`, outputs in `scratch/probe_gdelt/`*

## Method (minimal cost, by design)
40 real corporate-event contracts (vol > \$10k, 22 companies). One budget-gated BigQuery over
`gkg_partitioned`, partition-pruned to ±2 days around each event (dry-run \$0.051, hard-aborts > \$0.50).
Bounded body-text scrape of 120 primary-journalism URLs at concurrency 4. Timestamp-binding computed
from existing bars (no new cost).

## Findings

| dimension | result | read |
|---|---|---|
| Event coverage | **31/40 events (77.5%)** have GDELT hits within ±2 days | decent; 9 events had nothing |
| Corpus volume | 1.04M hits / 952k unique URLs | abundant in aggregate |
| Source quality | **1.2% primary journalism**, 90.4% long-tail "other", 7.5% aggregator | buried in noise, but ~285 primary URLs/event in absolute terms |
| Body-text yield | **69.2%** scrape success on primary URLs (median ~4,200 chars) | workable; ~31% lost to paywalls (the best sources) |
| **Timestamp binding** | market median inter-trade gap **24 min**, ~4 trade-hours/active day; GDELT is day-precision | **day-precision is ~60× too coarse to align cause/effect around events** |

## Verdict

**GDELT + scraping is a viable bootstrap, not a substitute for a licensed newswire.**

- **Use GDELT now:** source-filter to primary journalism → scrape (~69% yield) → a few thousand
  usable articles. Enough to **build/validate the matching pipeline (Thread 1)** and run a
  **first-cut coarse-resolution reaction study**. Free, unblocks work immediately.
- **Newswire is justified for the precision pass**, on two grounds scraping cannot fix:
  (1) **timestamps** — day-precision vs a 24-minute market resolution; (2) **paywalled full text +
  coverage bias** — the 31% scrape failures and 22% uncovered events are the highest-quality sources.
- **Not blocking:** proceed on GDELT+scraping; layer the newswire in for the final intraday study.

## Correction to the earlier framing
The prior deck/email leaned on "minute timestamps" generically, then I hedged that sparsity made them
less important. The probe shows the hedge was wrong: the market resolves at ~24 min around events, so
timestamp precision **does** bind. The newswire pitch should lead with the **24-minute market
resolution** number, not a generic timestamp claim.
