# Morning Report — Overnight Autonomous Run

*Prepared 2026-09-06 for the late-September data review. Goal was to advance Prof. Kelly's
deliverables as far as possible without you, using the universe pipeline.*

## TL;DR

**The core deliverable is done on real data.** The company universe is built (6,928 contracts), the
dead trade source was diagnosed and replaced, **594,984 real trades** were pulled and turned into
**72.5M log-odds bars**, and the five reaction visuals are computed. Headline finding: **a real
Polymarket reaction is mostly flat, punctuated by large jumps — 74.6% of 6h windows are zero-move
even in liquid markets.** The three-question deck and a Bryan email draft are written and reviewable.
**Two things need you; nothing else is blocked.**

## Kelly's asks → status → evidence

| # | Ask | Status | Evidence |
|---|---|---|---|
| Q1 | Usable market sample | ✅ done | `data/polymarket/universe.parquet` (6,928 contracts / 86 companies / 628 groups), `contract_groups.parquet` |
| Q2a | Trades + bars | ✅ done | 594,984 trades (Data-API), 72.5M bars; `src/polymarket/dataapi.py`, `trade_source_decision.md` |
| Q2b | Liquidity screen | ✅ done | `data/polymarket/liquidity_screen.parquet` |
| Q3 | Five log-odds visuals + read | ✅ done (real data) | `reports/figures/*_company.png`, `reports/logodds_eda_read.md` |
| Q4 | GDELT coverage audit | ✅ done | `reports/gdelt_coverage_audit.md` (94.2% company coverage) |
| Q5 | Reuters request | ✅ done | `reports/reuters_data_request.md` |
| Q5 | Three-question deck | ✅ done | `reports/data_review_deck.md` |
| — | Bryan email (consolidation) | ✅ drafted (not sent) | `reports/bryan_email_draft.md` |
| — | Yale compute access | ✅ researched + corrected | `reports/yale_cluster_request.md` (Bouchet, not McCleary) |
| — | Colab offload plan | ✅ done | `reports/colab_offload_plan.md` |

## Key findings

1. **Universe:** 6,928 company contracts, 86 companies, 2024-04 → 2026-08. Families: price_ladder
   6,174 · corporate_event 470 · revenue_ladder 170 · valuation_ladder 110 · market_cap_ladder 4.
   Liquidity is concentrated: \$79M total, top 500 markets = 63% of volume.
2. **Reaction (the core result):** on the liquid subset (vol > \$10k, 1,452 markets, 72.5M bars),
   **74.6% of 6h windows are zero-move** (mean ≈ 0, std 0.44). But non-zero moves are large (median
   |Δ| = 0.41 log-odds, tail to 5+). The reaction is **real but sparse** → the target should be
   event-/trade-conditioned, not a fixed 6h clock grid. Per-contract median 154 trades / 14 active
   days; a clean set (≥200 trades & ≥10 active days) = **473 contracts**.
3. **Matching:** GDELT covers 94% of companies. A \$0.05 validation probe
   (`reports/gdelt_validation_probe.md`, `fig6`) settled the "do we already have GDELT?" question:
   GDELT + scraping is a viable **bootstrap** (77.5% event coverage; 1.2% primary journalism but
   ~285 primary URLs/event; 69% body-scrape yield) — **enough to build the matching pipeline now** —
   but **not** the intraday corpus: the market resolves in **~24-minute** steps, so GDELT's
   day-precision timestamps bind (~60× too coarse), and 31% of the best sources are paywalled. A
   newswire is justified for the **precision pass**, pitched on the 24-minute number.

## The trade-source story (why this took the night)

The pipeline's trade source (Goldsky subgraph) was **permanently deprecated** (Polymarket V2
migration). I evaluated replacements, **decided on the official Polymarket Data-API `/trades`**
(free, complete — reconciles to the penny against known volume, loud 400 cap so no silent
truncation), and built + wired it (`src/polymarket/dataapi.py`, scripts 02/03). Full rationale and
the rejected options (Goldsky Edge, paid vendors with too-short history) are in
`reports/trade_source_decision.md`.

Getting the pull to complete took several root-cause fixes (all committed to the code, no
workarounds): 408-timeout handling + window-bisection; a durable resume (skip-if-exists + stable
cache keys) after I found the cache was keyed on `now()`; and an order-agnostic trade window after
6 markets turned out to have a corrupt `created_at`. **The dominant real obstacle was this machine's
internet dropping repeatedly** — the durable-resume fix means no work was ever lost, but if the
local connection stays flaky, the reliable venue for future heavy pulls is Colab/Bouchet.

## Open decisions (ranked — yours)

1. **Reaction target** — deferred to you per instruction. Evidence + 3 options in the deck Q2
   (shorten Δ / event-conditioned sampling / filter to the clean 473). My lean: event-conditioned.
2. **Public vs. private companies** — keep valuation-ladder private names (deep ladders, thin news)
   or restrict to public equities?
3. **Liquidity threshold** — the EDA used vol > \$10k for the bar build; confirm the modelling cut.
4. **Newswire** — resolved to *bootstrap-on-GDELT now, newswire for the intraday precision pass*
   (probe-verified). Still to choose: route (Yale-library entitlement vs. direct academic request).

## Two action items for you (nothing else is blocked)

1. **Reuters/newswire access** — approve/route the request in `reuters_data_request.md`.
2. **Bouchet sponsorship** — confirm you'll approve the YCRC account-confirmation email so I can
   submit the form (`yale_cluster_request.md`).

## Conviction per deliverable

| deliverable | conviction |
|---|---|
| Universe (Q1) | 8/10 |
| Trades/bars/liquidity (Q2a/b) | 9/10 (reconciled to the penny) |
| Reaction EDA (Q3) | 8/10 for the data; target choice is yours |
| GDELT audit (Q4) | 9/10 |
| Deck / email / requests | 8/10 (drafts for your review) |

## Honest caveats / what's NOT done

- **EDA is on the liquid subset (1,452 of 6,486 traded markets), not the full universe** — a
  deliberate disk/memory choice (full set = 181M bars / 7.2GB at 97% disk). Thin markets are
  characterised via the discovery-level liquidity table, not dense bars. Extending is a config flag
  (`--min-volume`) away once there's disk headroom.
- **6 markets have a corrupt `created_at`** (script-01 fell back to scrape date) → they were
  excluded from bars. Minor; a script-01 parse fix is the clean remedy.
- **Universe completeness caveat:** high-volume 2026 days hit Gamma's ~2,100 page ceiling; a few
  company contracts on those days may be undercounted (likely small — mostly excluded sports).
- **Event-time (fig5) uses synthetic events** — real event-time reactions need the article-matching
  pipeline (Q3 / newswire).
- **🔴 Machine disk at ~97% (17 GB free)** and **local network is flaky** — both worth addressing;
  neither is a repo problem.
- The reaction **target is intentionally not fixed** (your call).
