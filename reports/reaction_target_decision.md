# Reaction Target & Liquidity Cut — Decision Memo

*Weeks 7-9 Task B · drafted 2026-09-20 · status: **DECIDED — Δ=24h primary target; vol>$10k liquidity cut***

> **RESOLUTION:** primary reaction target is **y_logit_24h**. 1h/6h stay computable and are kept
> (per the earlier "explore all 3 reaction targets" decision), but only on the small
> minute-precision subset, with an explicit small-n caveat — they are secondary/exploratory, not
> the headline result. Liquidity gate for the main sample is **volume > \$10,000 (1,452
> contracts)**; the stricter **≥200 trades & ≥10 active trading days (473 contracts)** set is a
> verified nested subset of the 1,452, used for robustness checks, not a competing definition.

---

## 1. Why Δ=24h, not 1h/6h, is primary

**The corpus that will dominate matched articles is day-precision, and the pipeline already hard-disables sub-day windows for it.** Two independent, already-built facts force this:

1. `src/analysis/reaction_windows.py::compute_reaction_windows` (lines 49–53):
   ```python
   # Day-precision articles can only anchor 24h windows
   if timestamp_precision == "day" and delta_h < 24:
       result[key_y] = None
       result[key_v] = False
       continue
   ```
   This is not a target choice — it's an existing invariant (`CLAUDE.md`: *"GDELT timestamps are
   tagged `timestamp_precision = 'day'` — never treat them as minute-precise"*). Any GDELT-sourced
   article gets `valid_1h = valid_6h = False` unconditionally; only `valid_24h` can ever be `True`
   for it.

2. **The corpus is overwhelmingly GDELT.** Task A's real pull (`data/news/gdelt_gkg/`, verified
   2026-09-20) has **546,543 day-precision rows** across 86 companies. The RSS/feed corpus
   (`data/news/feeds/`) — the only source of `timestamp_precision="minute"` articles — currently
   has **115 rows total**, all minute-precision. That is a **~4,750:1** ratio of day- to
   minute-precision raw articles before matching narrows either set further. A 1h/6h target as the
   *primary* result would therefore be evaluated on well under 1% of the eventual matched corpus
   by construction — not a data problem to fix, a structural fact about the sources.

**Additional motivation, independent of precision:** the Q2 data-review finding
(`reports/data_review_deck.md`) that **74.6% of 6-hour windows have |Δ| < 0.01 log-odds** even on
the liquid subset — inactivity/LOCF manufactures zeros at a fixed 6h clock grid. A coarser 24h
window is less dominated by this dead-zone (more trading activity accumulates in the window),
which independently favors 24h as the primary target on top of the precision argument.

**What stays true:** the earlier "explore all 3 reaction targets" decision is not reversed. 1h/6h
remain implemented and computable — just restricted to the minute-precision RSS subset, and
reported as exploratory/small-n, never as the headline number. Flag this explicitly wherever 1h/6h
results appear: **n will be small** (currently 115 raw RSS articles before matching/verification
narrows it further — plausibly a few dozen verified matches, not hundreds).

---

## 2. Liquidity cut: volume > \$10,000 is the governing definition

From `data/polymarket/liquidity_screen.parquet` (verified directly, 2026-09-20) and
`reports/data_review_deck.md` Q1/Q2:

| volume floor | contracts | share of 6,486 traded markets |
|---|---|---|
| > \$0 | 6,486 | 93.6% |
| > \$1,000 | 4,875 | 70.4% |
| > \$5,000 | 2,559 | 36.9% |
| **> \$10,000** | **1,452** | **21.0%** |
| > \$50,000 | 243 | 3.5% |

**> \$10,000 (1,452 contracts) is the governing liquidity gate** for the main analysis sample —
this is the same cut the five Q2 EDA visuals (`fig1`–`fig5`) were already computed on, so keeping
it as the definition means the existing EDA stays representative of the modelling sample rather
than needing to be redone on a different cut.

### The 473-contract set is a nested stricter subset, not a conflicting definition

`reports/data_review_deck.md` also reports a stricter "clean" set: **≥200 trades AND ≥10 active
trading days = 473 contracts (32.6%)**. I verified directly (not re-stated from the deck) that
this is a **strict subset of the 1,452**, computed *within* the liquid set:

```
liquidity_screen.parquet: 1,452 rows (all volume > $10k)
  median n_trades = 154, median active_trading_days = 14
  pass rate n_trades >= 200:            40.0%
  pass rate active_trading_days >= 10:  58.2%
  pass rate BOTH (the "clean" set):     473 / 1,452 = 32.6%
```

So there is no conflict to resolve: **1,452 (vol > \$10k) is the sample-definition gate**; **473
(≥200 trades & ≥10 active days) is a stricter robustness subset** used to check that results
aren't artifacts of thin-but-technically-liquid contracts. Use 1,452 for the primary modelling
sample; re-run key results on the 473-contract subset as a robustness check, not as an alternative
primary definition.

---

## 3. What this does NOT decide

- **Public vs. private company panels** — separate open decision (`reports/gdelt_coverage_audit.md`
  §7, `memory/weeks_7_9_decisions.md`: keep both). Unaffected by this memo.
- **Newswire vs. GDELT-only corpus** — still under review pending the Reuters request
  (`reports/reuters_data_request.md`). If a newswire with minute-precision timestamps is added
  later, the 1h/6h sample size argument above should be revisited — it's a function of what's on
  disk today, not a permanent ceiling.
- **Trade-/event-conditioned sampling** (Q2 option 2, not filtering on a fixed clock grid) — still
  open; orthogonal to the Δ choice made here, since day-precision anchoring at Δ=24h works
  identically whether the underlying bars are read on a fixed grid or event-conditioned.
