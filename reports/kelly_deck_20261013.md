---
marp: true
theme: default
paginate: true
size: 16:9
---

# News Shocks in Prediction Markets
### Thread 1 + Thread 2 results, real data, 2026-10-13

Avi Kabra

---

## Context

- Question: does company news predictably move Polymarket company-stock contracts, and can two *new* methods (not off-the-shelf) measure and predict that reaction?
- Data: 6,928 resolved contracts / 86 companies (Apr 2024–Aug 2026), matched against 546,657 GDELT articles (day-precision only, ~1% primary journalism)
- Reaction target: `y_logit_24h` only — GDELT's day-precision rules out 1h/6h windows by design, not by gap

---

## Method refresher

- **Thread 1 (matching):** `match_quality = w1·logit(cosine) + w2·z(volume_spike)` → `sigmoid`, w1=w2=1 fixed, validated out-of-sample against realized `|y_logit_24h|`
- **Thread 2 (ladder consistency):** weighted isotonic (PAVA) projection of each cohort's independent 24h reactions, monotone in strike, volume-weighted
- Both are genuinely joint (not post-hoc smoothing) and both ship with a required out-of-sample acceptance test — see `novel_math_design.md`

---

## Thread 1: matching — accepted result

| Score | Spearman ρ vs realized &#124;y_logit_24h&#124; | n |
|---|---|---|
| Embedding-only (cosine) | 0.233 | 14,717 |
| Joint (embedding + liquidity) | **0.509** | 14,717 |

- Both p ≈ 0; joint score roughly doubles embedding-only correlation
- Entity-grounding extension (w3·1[name in article]) tested same-pass, same-data: ρ dropped to 0.451 — **rejected, reverted from production**
- Accepted formula: the two-term version above

---

## Thread 2: ladder consistency — real effect, no predictive gain

| Category | Mean &#124;correction&#124; (log-odds) | R² raw → R² ladder-corrected |
|---|---|---|
| Price-target | 0.562 | 0.084 → 0.073 |
| Valuation | 0.287 | 0.746 → 0.363 |
| Revenue | 0.610 | n=34, too thin to test |
| Corporate event | 0.000 (singleton, by design) | — |

- The correction is large and real (cohort-level isotonic pooling genuinely changes values)
- It does not improve 5-fold CV predictive fit for either testable category — reported as a negative result, not hidden

---

## Model comparison: R² (test, out-of-sample)

| Category | Linear | LSTM | Transformer | TCN | n (test) |
|---|---|---|---|---|---|
| All (pooled) | −0.010 | −0.016 | −0.175 | −0.078 | 5,151 |
| Corporate event | −0.021 | −0.060 | −0.062 | −0.084 | 3,157 |
| Price-target | −0.001 | **+0.010** | +0.003 | −0.026 | 598 |
| Revenue-target *(new)* | −0.101 | −0.054 | −0.029 | −0.016 | 9 (train 19) |
| Valuation | −0.255 | — | — | — | linear only |

- Baseline = real test-period mean (not a blind train-mean forecast) — an easy bar, mostly not cleared
- Revenue-target trained for the first time this round (own rank-based split; shared global cutoff gave it 0 train rows)

---

## The bug: degenerate bootstrap CIs, found and fixed

- `parent_event_id` was hardcoded `None` at the source (Gamma API parser) — collapsed the block-bootstrap to one cluster → every CI was zero-width
- Fix: the real event ID was already in Gamma's raw response (`events[0].id`), just never read — backfilled 2,777/6,928 markets (40.1%, 546 real events) → 24 real clusters in the final test set

| H | Claim | Before | After |
|---|---|---|---|
| H1 | richer embeddings beat raw | Supported | **Not supported** |
| H2 | best arch differs by category | Not supported | Not supported |
| H3 | quantitative articles beat high-attention | Supported | Supported (n=28) |
| H4 | best ladder beats corporate_event | Supported | **Not supported** |

---

## Scoping decisions (made explicitly, not left implicit)

- **market_cap_ladder** (4 markets): dropped entirely — too small to mean anything
- **valuation_ladder** (110 markets): kept, flagged below the gate's 200-market floor — everything else about it clears the gate comfortably
- **revenue_ladder**: fixed properly rather than excluded — given its own rank-based split (not the shared global cutoff), now has real trained models across all 4 architectures

---

## Limitations

- GDELT-only feed (no licensed newswire) and its day-precision ceiling are structural, deliberate tradeoffs — 24h is the only defensible reaction window with this feed, not a gap to close
- `resolved_at` / `parent_event_id` are each only ~40% backfilled from Polymarket's API — fallbacks cover the rest, not a blocker
- `revenue_ladder`'s real numbers rest on 19 training / 6 validation examples — real, but small; treat as directional, not conclusive

---

## Outstanding questions for Kelly

- Is the 200-market feasibility floor the right bar, or should `valuation_ladder`'s caveat be the standard going forward for small-universe categories?
- Given only H3 survives real statistical scrutiny — does the thesis lead with Thread 1 (clean win) and frame H1–H4 as a secondary, mostly-null robustness check?
- Worth a newswire budget ask, or is the GDELT-only story (and its limits) the final answer for this thesis?
