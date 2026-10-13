---
marp: true
theme: default
paginate: true
size: 16:9
---

# News Shocks in Prediction Markets
### Real results, 2026-10-13

Avi Kabra

---

## Context

- Does company news predictably move Polymarket company-stock contracts? No existing tool answers this directly, so this project builds two new methods.
- Data: 6,928 resolved contracts across 86 companies (Apr 2024-Aug 2026), matched against 546,657 GDELT articles
- GDELT only timestamps articles to the day, so every result below measures the 24-hour price reaction, the only window this feed supports

---

## Method

**Matching** picks the right article for a contract, combining text similarity and trading-volume spikes:

match_quality = w1 &middot; logit(cosine similarity) + w2 &middot; z(volume spike), then sigmoid

**Consistency** forces a company's related contracts (above $150, $160, $170) to react in the same direction, weighted by volume, via isotonic regression (PAVA).

Both are new methods built for this problem, not off-the-shelf tools, and both are validated on real held-out data below.

---

## Result 1: the matching method works

| Method | Spearman &rho; vs. actual price move | n |
|---|---|---|
| Matching score (text + volume) | **0.509** | 14,717 |
| Text similarity alone | 0.233 | 14,717 |

Given a list of candidate articles for a contract, this score reliably tells us which one actually explains the price move. Text alone is close to a coin flip; the combined score is not.

---

## Result 2: the consistency correction doesn't help, so we don't use it

| Category | R&sup2;, raw reaction | R&sup2;, after correction |
|---|---|---|
| Price-target | 0.084 | 0.073 |
| Valuation | 0.746 | 0.363 |

The correction shifts values by a real amount but makes predictions worse in both testable categories. We predict from the raw reaction, not the corrected one.

---

## Result 3: none of the four models give a usable edge

| Category | Best model | R&sup2; | n (test) |
|---|---|---|---|
| All (pooled) | Linear | &minus;0.010 | 5,151 |
| Corporate event | Linear | &minus;0.021 | 3,157 |
| Price-target | LSTM | **+0.010** | 598 |
| Revenue-target | TCN | &minus;0.016 | 9 |
| Valuation | Linear only | &minus;0.255 | small |

No category clears a plain guess-the-average baseline by a meaningful margin. Revenue-target is trained here for the first time, on its own data split, and still lands negative.

---

## Result 4: one of four pre-registered predictions holds up

| Prediction | Result |
|---|---|
| Richer embeddings beat simpler ones | Not supported |
| Best model differs by category | Not supported |
| Quantitative articles beat high-attention ones | Supported (n=28) |
| Best ladder category beats corporate events | Not supported |

Tested with bootstrap resampling clustered by real-world event, so duplicate coverage of one story doesn't count as independent evidence. Only the third prediction survives, on a small sample.

---

## Scoping decisions

- **market_cap_ladder** (4 markets): dropped, too small to mean anything
- **valuation_ladder** (110 markets): kept, flagged as below our 200-market floor, everything else about it clears comfortably
- **revenue_ladder**: given its own data split so it could be trained at all, rather than excluded

---

## Limitations

- GDELT is free but noisy, and day-precision is a structural limit of this feed, not a gap to close
- `resolved_at` and `parent_event_id` are each about 40% backfilled from Polymarket's API; fallbacks cover the rest
- The revenue-target result rests on 19 training examples: real, but small

---

## Recommendation

- Lead the thesis with the matching result (Result 1): it is the clean, strong, genuine contribution
- Present the consistency correction and the model comparison as honest negative results, not failures
- Keep the 200-market floor as the rule, with `valuation_ladder` as a documented, explicit exception
- A licensed newswire is the single highest-leverage next step if budget allows; everything else here is close to final
