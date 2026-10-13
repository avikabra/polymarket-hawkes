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

## Result 1: contracts do react to news

| Method | Spearman &rho; vs. actual price move | n |
|---|---|---|
| Matching score (text + volume) | **0.509** | 14,717 |
| Text similarity alone | 0.233 | 14,717 |

This is half the answer to our question: a company's news and its market's trading behavior are measurably linked. Every later result depends on this step, it is how we built a trustworthy dataset of article-reaction pairs at all.

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

## So, does Polymarket respond to news shocks?

**Yes, but only partly.** There is a real, strong relationship between an article and the price move it precedes (Result 1): when we can identify the right article, the market has reacted.

**That reaction is not predictable in advance.** Every model found essentially no exploitable signal (Results 2-4). The market absorbs news efficiently enough that we cannot forecast the size or direction of the reaction ahead of time, with the tools and data available here.

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
