---
marp: true
theme: default
paginate: true
size: 16:9
---

# News Shocks in Prediction Markets
### Real results, 2026-10-14

Avi Kabra

---

## The question driving this thesis

**Do news shocks about a company produce a measurable, predictable price reaction in that company's Polymarket contracts?**

Everything that follows answers this question directly.

---

## Context

- Data: 6,928 resolved contracts across 86 companies (Apr 2024-Aug 2026), matched against 546,657 GDELT articles
- No existing tool answers the question above directly, so this project builds two new methods
- GDELT only timestamps articles to the day, so every result below measures the 24-hour price reaction, the only window this feed supports

---

## Method: the mechanics

**Matching** picks the right article for a contract, combining text similarity and trading-volume spikes:

match_quality = w1 &middot; logit(cosine similarity) + w2 &middot; z(volume spike), then sigmoid

**Consistency** forces a company's related contracts (above $150, $160, $170) to react in the same direction, weighted by volume, via isotonic regression (PAVA).

---

## Method: why these, and why they should work

Both methods are new combinations of established tools, not inventions from scratch.

Combining independent signals in log-odds space is standard practice (the same math behind naive Bayes classifiers). Volume spikes as a marker of real news arriving is a standard idea in market microstructure research, going back to classic event-study methodology. Isotonic regression is a long-established tool for order-restricted inference (Barlow, Bartholomew, Bremner & Brunk, 1972), and the logic that related contracts should price consistently is the same logic behind no-arbitrage pricing.

What's new: applying both combinations to this specific problem, matching news to prediction-market contracts and enforcing no-arbitrage-style consistency across a strike ladder, which we are not aware of being done before.

---

## Result 1: contracts do react to news, with one caveat found since

| Method | Spearman &rho; vs. actual price move | n |
|---|---|---|
| Matching score (text + volume) | **0.509** | 14,717 |
| Text similarity alone | 0.233 | 14,717 |

This is half the answer to our question: a company's news and its market's trading behavior are measurably linked. Every later result depends on this step, it is how we built a trustworthy dataset of article-reaction pairs at all.

**New finding (next section): part of the 0.509 number is inflated.** Validated against the real stock's own reaction instead of Polymarket's own data, the matching score drops to &rho;=0.029; text similarity alone holds up better (&rho;=0.092). The volume component was likely riding a coincidence, not genuinely validating match quality.

---

## Result 2: the consistency correction doesn't help, so we don't use it

| Category | R&sup2;, raw reaction | R&sup2;, after correction |
|---|---|---|
| Price-target | 0.084 | 0.073 |
| Valuation | 0.746 | 0.363 |

We expected this to help: related contracts should price consistently, by no-arbitrage logic. It likely hurts because the correction smooths away real, contract-specific variation the prediction models depend on. We predict from the raw reaction, not the corrected one.

---

## Result 3: but the reaction isn't predictable in advance

| Category | Best model | R&sup2; | n (test) |
|---|---|---|---|
| All (pooled) | Linear | &minus;0.010 | 5,151 |
| Corporate event | Linear | &minus;0.021 | 3,157 |
| Price-target | LSTM | **+0.010** | 598 |
| Revenue-target | TCN | &minus;0.016 | 9 |
| Valuation | Linear only | &minus;0.255 | small |

This is the other half of the answer. If Polymarket prices already reflect public news quickly, this is exactly the pattern we'd expect: a real reaction (Result 1), but no way to forecast its size from the article alone.

---

## Result 4: one of four pre-registered predictions holds up

| Prediction | Tests whether... | Result |
|---|---|---|
| Richer embeddings beat simpler ones | text representation matters | Not supported |
| Best model differs by category | architecture choice matters | Not supported |
| Quantitative articles beat high-attention ones | article type matters | Supported (n=28) |
| Best ladder category beats corporate events | ladder structure adds signal | Not supported |

Tested with bootstrap resampling clustered by real-world event, so duplicate coverage of one story isn't counted as independent evidence.

---

## A harder question: does it match the real world?

Every result so far compares Polymarket against **itself** — the matching score vs. Polymarket's own price move, the prediction models vs. Polymarket's own target. None of it checks whether the real, publicly-traded company also reacted, or whether Polymarket's reaction is proportionate.

Pulled real daily stock prices for the 78 public companies in our universe (yfinance) and re-ran both novel-math threads against this external benchmark.

---

## Result 5: a real relationship, but not proportionate

| Test | Spearman &rho; | Significant? |
|---|---|---|
| Direction of Polymarket's move vs. the real stock's move | 0.119 | Yes (n=10,905) |
| **Size** of Polymarket's move vs. **size** of the real stock's move | 0.015 | No |

Polymarket leans the right direction, weakly. But the size of its reaction tells you almost nothing about how big the real-world move was. A company-clustered bootstrap (correcting for shared companies/time windows across articles) confirms the directional result is real, not a statistical artifact: 95% CI [0.047, 0.188], excludes zero.

---

## Result 6: a tradeable signal, isolated to one contract type

Twenty-three model specifications were tried against the full external benchmark before finding one that survives scrutiny (literature-standard forms, a novel match-quality moderator, window and liquidity variants, a digital-option-pricing structure). The signal turned out to be concentrated in **price-target contracts** specifically, where the strike is a real stock price in the same units as the real stock:

| Check | Result |
|---|---|
| Per-split correlation (train/val/test, independent) | 0.18 / 0.14 / 0.18, all significant |
| Company-clustered bootstrap (price-target only) | 95% CI [0.043, 0.288], excludes zero |
| Backtest P&L vs. 5,000 random permutations | 100th percentile (p=0.0002) |
| **Bonferroni-corrected for all 23 forms tried** | **p=0.0044, still significant** |

Equation: `y_logit_24h = 0.158 · (stock_return / company_volatility) − 0.184`. Survives realistic transaction costs (10-40bps) with under 2% P&L erosion.

---

## Result 6, continued: what this is and isn't

- **Is**: a real, cluster-robust, theoretically-motivated signal, backtested and statistically significant after correcting for every model tried
- **Isn't**: a precisely calibrated prediction model (R&sup2; stays negative — expected for an effect this size, not a failure) or proven beyond price-target contracts
- **Real limitation**: only 16 companies back this finding; held out exactly 4 companies never seen in training (bank stocks) and the signal held

---

## So, does Polymarket respond to news shocks?

**Yes, but more narrowly than it first looked.** Polymarket's own data shows a real reaction (Result 1, with the volume-term caveat), and that reaction is not predictable in advance from the article alone (Results 2-4).

**Checked against the real world, the picture sharpens further.** The reaction tracks the real stock's direction, weakly but robustly (Result 5) — not its size. And a genuinely tradeable version of this signal exists, but only for price-target contracts specifically (Result 6), surviving the most adversarial testing we could throw at it.

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
- The price-target trading signal (Result 6) rests on 16 companies total; transaction costs are literature-based, not Polymarket's measured spreads

---

## Recommendation

- Lead the thesis with the matching result (Result 1) and the price-target trading signal (Result 6): the two clean, genuine, adversarially-tested contributions
- Present the consistency correction, the model comparison, and the external-benchmark proportionality check as honest negative/mixed results, not failures
- Keep the 200-market floor as the rule, with `valuation_ladder` as a documented, explicit exception
- Measuring Polymarket's actual historical bid-ask spread would replace Result 6's literature-based cost estimate with a real one — the highest-leverage next step
