---
marp: true
theme: default
paginate: true
size: 16:9
math: katex
---

# News Shocks in Prediction Markets

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

$$\text{match\_quality} = w_1 \cdot \text{logit}(\text{cosine similarity}) + w_2 \cdot z(\text{volume spike})$$
$$\text{match\_confidence} = \text{sigmoid}(\text{match\_quality})$$

**Consistency** forces a company's related contracts (above $150, $160, $170) to react in the same direction, weighted by volume, via isotonic regression (PAVA):

$$\min \sum_i v_i (y_i - r_i)^2 \quad \text{subject to} \quad y_1 \le y_2 \le \dots \le y_n$$

---

## Method: why these, and why they should work

Both methods are new combinations of established tools, not inventions from scratch.

Combining independent signals in log-odds space is standard practice (the same math behind naive Bayes classifiers). Volume spikes as a marker of real news arriving is a standard idea in market microstructure research, going back to classic event-study methodology. Isotonic regression is a long-established tool for order-restricted inference (Barlow, Bartholomew, Bremner & Brunk, 1972), and the logic that related contracts should price consistently is the same logic behind no-arbitrage pricing.

What's new: applying both combinations to this specific problem, matching news to prediction-market contracts and enforcing no-arbitrage-style consistency across a strike ladder.

---

## Result 1: contracts do react to news, with one caveat found since

| Method | Spearman &rho; | n |
|---|---|---|
| Matching score (text + volume) | **0.509** | 14,717 |
| Text similarity alone | 0.233 | 14,717 |

This is half the answer to our question: a company's news and its market's trading behavior are measurably linked. Every later result depends on this step, it is how we built a trustworthy dataset of article-reaction pairs at all.

**New finding (next section): part of the 0.509 number is inflated.** Validated against the real stock's own reaction instead of Polymarket's own data, the matching score drops to &rho;=0.029; text similarity alone holds up better (&rho;=0.092). The volume component likely rode a coincidence specific to Polymarket's own data.

---

## Result 2: the consistency correction makes predictions worse

| Category | R&sup2; (raw) | R&sup2; (corrected) |
|---|---|---|
| Price-target | 0.084 | 0.073 |
| Valuation | 0.746 | 0.363 |

We expected this to help: related contracts should price consistently, by no-arbitrage logic. The correction smooths away contract-specific variation the prediction models depend on, so we predict from the raw reaction.

---

## Result 3: models land close to guessing the average

| Category | Best model | R&sup2; |
|---|---|---|
| All (pooled, n=5,151) | Linear | &minus;0.010 |
| Corporate event (n=3,157) | Linear | &minus;0.021 |
| Price-target (n=598) | LSTM | **+0.010** |
| Revenue-target (n=9) | TCN | &minus;0.016 |
| Valuation (small n) | Linear only | &minus;0.255 |

This is the other half of the answer. If Polymarket prices already reflect public news quickly, this is exactly the pattern we'd expect: a reaction (Result 1) whose size depends on information beyond the article itself.

---

## Result 4: one of four pre-registered predictions holds up

| Prediction | Result |
|---|---|
| Richer embeddings beat simpler ones | Not supported |
| Best model differs by category | Not supported |
| Quantitative articles beat high-attention ones | Supported (n=28) |
| Best ladder category beats corporate events | Not supported |

---

## Result 5: Polymarket tracks the real stock's direction

| Test | Spearman &rho; | 95% CI |
|---|---|---|
| Direction vs. direction | **0.119** | [0.047, 0.188] |
| Size vs. size | 0.015 | includes zero |

CI from a company-clustered bootstrap. A company can show a huge real-world move alongside a tiny Polymarket reaction, or the reverse.

---

## Result 6: a tradeable signal, for price-target contracts

$$\text{reaction} = \kappa \cdot D \cdot \frac{\text{stock return}}{\text{stock volatility}} + \delta$$

| Term | Value |
|---|---|
| D (theoretical sensitivity) | 1.702 |
| &kappa; (efficiency ratio) | 0.093 |
| &delta; (baseline drift) | &minus;0.184 |

D is a known constant (Birnbaum 1968), not fit to our data: the slope a frictionless digital option would have. These contracts move at about 9% of that rate. &delta; is the 24h drift with no stock move, consistent with favorite-longshot overpricing correction (Snowberg & Wolfers 2010).

---

## Result 6: validated and backtested

| Check | Result |
|---|---|
| Correlation across train / val / test | 0.18 / 0.14 / 0.18 |
| Company-clustered bootstrap | 95% CI [0.043, 0.288] |
| Backtest vs. 5,000 random permutations | 100th percentile |
| Bonferroni-corrected across 23 models tried | p=0.0044 |

Mean P&L of +0.042 log-odds per trade, Sharpe ratio 0.245 per trade. Keeps 98%+ of that profit under realistic trading costs (10-40bps), concentrated in a few large moves rather than spread evenly. Spans 16 companies, including 4 banks absent from training.

---

## So, does Polymarket respond to news shocks?

**Yes, and the picture sharpens as we look closer.** Polymarket's own data shows a reaction (Result 1); every model we tested lands close to guessing the average (Results 2-4).

**Checked against the real world, Polymarket's reaction tracks the real stock's direction (Result 5).** For price-target contracts, that relationship strengthens into a tested, tradeable signal (Result 6).

---

## Scoping decisions

- Market-cap contracts (4 markets): dropped, too few to draw a conclusion from
- Valuation contracts (110 markets): kept, below our 200-contract minimum sample size, but every other check passes
- Revenue contracts: given a separate data split so training was possible at all, instead of being excluded

---

## Limitations

- GDELT gives day-precision timestamps, a structural limit of this feed
- `resolved_at` and `parent_event_id` are each about 40% backfilled from Polymarket's API; fallbacks cover the rest
- The revenue-target result rests on 19 training examples
- The price-target trading signal (Result 6) spans 16 companies; transaction costs come from published research rather than Polymarket's measured spreads

---

## Next steps

- Measure Polymarket's actual historical bid-ask spread, to replace Result 6's cost estimate (currently from published research) with a real one
- Decide together how much weight Result 6 should carry given its narrow base (16 companies)
- Revisit the valuation-contract sample-size exception if more data becomes available
