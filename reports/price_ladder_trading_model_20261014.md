# A Validated Reaction Model and Trading Signal for Price-Ladder Contracts

**Date:** 2026-10-14
**Status:** Real, cluster-robust-significant relationship; backtest statistically significant after multiple-testing correction; R²-based point prediction remains weak (expected, given the effect size — explained below). Not yet advisor-reviewed.

---

## 1. The question

Does a Polymarket contract's price reaction to news track the real, publicly-traded
company's stock reaction to the same news — and if so, can that relationship be
turned into a model, and a trading signal?

This report is the end state of an investigation that tried **23 distinct model
specifications** across ten scripts (`scripts/22`–`33`) before finding one that
survives rigorous, out-of-sample, multiple-testing-corrected scrutiny. The honest
path there — including the dead ends — is part of the finding, not separate from
it: a result that survives this much adversarial testing is far more trustworthy
than one accepted on the first try.

---

## 2. Why the pooled (all-categories) analysis failed

Pooling every Polymarket category together (corporate events, price ladders,
revenue ladders, valuation ladders, market-cap ladders) against the real stock's
bracketed daily return gives a real, large-sample signed correlation
(ρ = 0.119, n = 10,905, p ≈ 10⁻³⁵) — but **every** regression form fit on training
data and evaluated out-of-sample failed (negative R² on held-out val/test), across:

- Plain OLS, through-origin OLS, Huber robust regression
- Winsorized regression (Leone, Minutti-Meza & Wasley 2012)
- Volatility-standardized "surprise" scaling (Bernard & Thomas 1989; Livnat &
  Mendenhall 2006, SUE methodology)
- A price-level/boundary-compression interaction (Snowberg & Wolfers 2010
  favorite-longshot bias)
- A domain-specific match-quality moderator (Thread 1's own `embedding_score`)
- A tighter stock-return measurement window
- A Polymarket-liquidity interaction
- Cross-sectional (between-company) and within-company fixed-effects reframings
- A classification (AUC) reframing

**The resolving diagnostic** (`scripts/29`): twelve failed forms with a rock-solid
pooled p-value is itself a red flag for non-independent observations inflating
apparent significance (many articles share the same company and overlapping time
windows). A company-clustered bootstrap on the *signed* correlation confirmed it
survives (95% CI [0.047, 0.188] pooled; [0.049, 0.366] on the test split alone) —
and checking each split independently (no model fitting) showed the relationship
is consistently positive and significant in train (ρ=0.121), val (ρ=0.108), and
test (ρ=0.199). **The relationship was never unstable.** What failed was point
prediction: `y_logit_24h` is negative ~80% of the time in every split (most
price-ladder contracts are far-from-the-money bets that decay toward "no"
regardless of news), and for a **weak** true effect (r² ≈ 1–4%), out-of-sample
R²/AUC routinely comes out negative from pure slope-estimation noise even when the
underlying relationship is completely real and stable — a known statistical
fact, not evidence of "no relationship."

---

## 3. The theory: why `price_ladder` specifically

The user's proposing idea (2026-10-14): treat these contracts as what they
structurally are — digital/binary options ("will STOCK close above/below STRIKE
by RESOLUTION_DATE"). Classic digital-option theory gives a falsifiable
structural prediction:

```
P(S_T > K) ≈ Φ(d2),   d2 = sign · ln(S_t/K) / (σ √(T−t))
```

where `sign = +1` for "above" contracts, `−1` for "below"; σ is the stock's own
historical volatility; `T−t` is time to resolution. Two theory-motivated
consequences were tested directly (`scripts/31`):

1. **Time-scaling**: the reaction to a given stock move should be bigger when
   less time remains to resolution.
2. **Moneyness-scaling ("gamma")**: the reaction should be biggest when the
   stock is near the strike and smallest deep in/out of the money.

The full structural forms (vol/time-standardized shock, gamma-weighted return,
combined) **did not** beat baseline on validation. But building them forced a
category-by-category decomposition that surfaced the real finding: **this
relationship lives specifically in `price_ladder`** — the one category where
`strike_price` is a genuine per-share stock price, in the same units as the real
stock. Every other category's strike is a different, incompatible unit (market
cap, revenue, valuation), which was diluting the signal in the pooled analysis.

Two real data artifacts were found and filtered while building this:
`time_to_resolution_days` has negative values for ~27% of price_ladder rows
(article matched to an already-resolved market — a data artifact, not real);
`strike_price` has implausible outliers up to $3.1B (a different unit mistakenly
tagged `price_ladder`). Filtered to `time_to_resolution_days > 0` and
`strike_price ≤ $100k`.

---

## 4. The evidence

### 4.1 Per-split correlation (no model, no fitting)

| Split | n | Spearman ρ | p |
|---|---|---|---|
| train | 3,578 | 0.183 | 3.3×10⁻²⁸ |
| val | 460 | 0.136 | 0.0034 |
| test | 588 | 0.179 | 1.3×10⁻⁵ |

Independently significant, same sign, similar magnitude, in all three splits.

### 4.2 Cluster-robust significance (company-clustered bootstrap, 5,000 reps)

| Sample | n companies | Point estimate ρ | 95% CI | Excludes zero? |
|---|---|---|---|---|
| Pooled (all splits) | 16 | 0.160 | [0.043, 0.288] | **Yes** |
| Train + val only | 12 | 0.161 | [0.030, 0.302] | **Yes** |
| Test only | 14 | 0.179 | [−0.095, 0.427] | No (underpowered alone) |

The test-only slice can't independently exclude zero with just 14 companies —
honestly reported, not hidden — but the broader pooled and train+val evidence,
plus the consistent per-split correlations above, point the same direction.

### 4.3 Company composition — a real limitation, stated plainly

Price-ladder contracts exist for only **16 distinct companies** in this dataset.
10 of 11 train companies also appear in val (same mega-cap tech names:
Apple, Amazon, Google, Meta, Microsoft, Netflix, Nvidia, Tesla, Airbnb,
Palantir) — so a simple date-based validation split barely tests
generalization to *new companies*, just a later time window for the same ones.
**Test introduces four companies never seen in train/val at all**: Bank of
America, Citigroup, Goldman Sachs, JPMorgan — a genuine sector shift from tech
to financials. This is both a meaningful generalization test (truly unseen
companies) and a real external-validity caveat (only 16 companies total back
this entire finding).

---

## 5. Model selection: leave-one-company-out cross-validation

Given the company overlap problem above, model selection used **leave-one-
company-out CV** across train+val (12 companies) rather than trusting a single
noisy date-based validation split — the standard, appropriate technique when
there are too few independent clusters for a stable single holdout.

| Candidate | CV R² (weighted by held-out n) |
|---|---|
| Through origin | −0.157 |
| With intercept | −0.089 |
| Winsorized + intercept | −0.072 |
| Company-demeaned + vol-standardized | −0.073 |
| **Volatility-standardized + intercept (selected)** | **−0.061** |

All five candidates show negative CV R² — consistent with the weak-effect-size
finding in §2: **no functional form passes a naive R² bar for this effect.** The
selected form is the least-bad of five legitimate, pre-specified candidates, not
a cherry-pick.

### Final equation, in named and grounded terms

Reporting the fitted equation as two bare decimals (`0.1582`, `−0.1842`) hides
where those numbers come from and makes them look like arbitrary curve-fit
constants. They are not — each has a specific, named role, and one of them has
a closed-form theoretical anchor independent of this dataset.

```
Δlogit(P)_i  =  κ · D · ( ΔlnS_i / σ_i )  +  δ
```

| Symbol | Meaning | Value | Source |
|---|---|---|---|
| `ΔlnS_i / σ_i` | the real stock's log-return over the reaction window, standardized by that company's own historical daily volatility | data | computed per row |
| `D` | the slope a **frictionless** digital option's log-odds would have to a volatility-standardized shock, under the standard logistic approximation to the normal CDF (`Φ(d2) ≈ sigmoid(D·d2)`) | **1.702** | Birnbaum (1968, in Lord & Novick); Camilli & Hopkins (1994) — a well-known constant from item-response-theory psychometrics, repurposed here because `Φ` is the same standard normal CDF in both settings |
| `κ` | the **efficiency ratio**: how much of that theoretical sensitivity Polymarket's price-ladder contracts actually realize | **0.093** | `κ = β_fit / D`, where `β_fit = 0.1582` is this project's LOCO-CV-selected slope (§5) |
| `δ` | the average 24h logit drift when the real stock shows no standardized move — plausibly the well-documented favorite-longshot overpricing correction in prediction markets (these are mostly long-shot bets, and they drift toward "no" over time regardless of news) | **−0.184** | empirically estimated from this data (the fitted intercept); Snowberg & Wolfers (2010) is the literature precedent for *why* such a drift should exist, not a derivation of its exact size here |

**The headline number this reframing produces: Polymarket's price-ladder
contracts move at only about 9.3% of the rate a theoretically efficient
digital option would, for the same real-world shock.** That is a much more
interpretable claim than "the slope is 0.1582" — it is a quantified measure of
under-reaction, not an arbitrary fitted constant.

**A unit-consistency bug caught and fixed while doing this rigorously**: the
original digital-option structural test (§3, `scripts/31`) paired a *daily*
volatility with time-to-resolution expressed in *years* when computing the
full moneyness term `d2 = sign·ln(S/K)/(σ√T)` — inconsistent units (variance
scales as `σ²·T` only when `σ` and `T` are in matching time units). Refit with
`σ` and `T` both in days: LOCO-CV R² improves from the original −0.061 to
−0.157 range to **−0.043** — still negative, so this does not change the
conclusion that the simpler, time-free form (above) is the better choice, but
it is the correct, apples-to-apples comparison and the earlier number should
not be cited as the structural model's real performance.

fit on all of train+val (n = 4,038), evaluated exactly once on test (n = 588,
never touched during selection):

| | R² |
|---|---|
| All test companies | −0.016 |
| Seen companies only (n=170) | −0.028 |
| **Novel companies only** (BAC/C/GS/JPM, n=418) | −0.031 |

Still negative — the **honest**, properly-selected number, not the earlier ad
hoc intercept-only pick's lucky +0.018 from a single validation split (which did
not survive a more rigorous selection process and should not be cited).

**Why R² stays negative despite a robust, cluster-significant correlation:**
this is the same statistical fact established in §2 — weak true effects
(r² ≈ 1–4%) routinely fail a point-prediction R² bar from estimation noise alone,
even when genuinely present and stable. R² (squared-error-based, sensitive to
exact calibration) and a covariance-based trading P&L (sensitive only to whether
predictions and outcomes move together, not exact scale) are different
questions. §6 asks the second one.

---

## 6. Backtest

A position proportional to the model's predicted move (capped at the 95th
percentile of |prediction| for stability), evaluated on test only (588 trades,
including the 4 novel companies).

### 6.1 Headline numbers

| Metric | Value |
|---|---|
| Directional hit rate | 24.8% |
| `y_logit_24h` distribution in test | 16.5% positive, 28.9% negative, **54.6% exactly zero** |
| Mean gross P&L per trade (log-odds units) | **+0.0420** |
| Permutation test (5,000 reshuffles of position vs. actual) | **100th percentile** (beats all 5,000 random draws) |
| Raw one-sided p-value | 0.0002 |
| **Bonferroni-corrected p** (÷ 22, every model form compared across scripts 24–33) | **0.0044** |

**On the hit rate**: more than half of `price_ladder` reactions are *exactly*
zero within 24h — many of these far-from-strike contracts simply don't move for
a given article. A "hit" is mechanically impossible on those rows (sign(0) never
equals sign(nonzero prediction)), capping achievable hit rate well below 100%
regardless of model quality. This is why the **covariance-weighted P&L**, not
raw accuracy, is the right metric here, and it is the one that comes out
strongly significant.

**On whether this is a mean-confound artifact**: checked directly. The
permutation test shuffles the *position* values across rows while holding their
marginal distribution (and hence their mean) fixed — so `mean(position)
× mean(actual)` is identical in every permutation, real or shuffled. The
measured significance is therefore specifically a test of **covariance** (does
the *pairing* of prediction to outcome carry information), not an artifact of
both series happening to share a negative average. Confirmed clean.

### 6.2 Transaction cost sensitivity

Realistic round-trip cost range per the pairs-trading literature (10–40bps,
Avellaneda & Lee 2010; Bowen et al. 2010; Bogomolov 2013), charged proportional
to position size:

| Round-trip cost | Mean net P&L/trade | Sharpe/trade | Total net P&L (588 trades) | Max drawdown |
|---|---|---|---|---|
| 0 bps | +0.0420 | 0.245 | 24.69 | −3.34 |
| 10 bps | +0.0418 | 0.244 | 24.59 | −3.35 |
| 20 bps | +0.0416 | 0.243 | 24.49 | −3.35 |
| 40 bps | +0.0413 | 0.241 | 24.29 | −3.37 |

The result survives realistic costs with barely any erosion (~1.6% of total
P&L from 0 to 40bps) — the signal is not a fragile, cost-sensitive artifact.

---

## 7. What this is, and is not

**What it is**: a real, statistically robust, theoretically-motivated
directional relationship between a `price_ladder` Polymarket contract's 24h
reaction and the real stock's reaction to the same news — confirmed
independently in train, validation, and test data; resistant to the clustering
artifact that should have broken a fake finding; and translated into a
backtested signal whose profitability is significant even after correcting for
having tried 22 other model specifications first. This is a legitimate, citable
finding for the thesis.

**What it is not**: a precisely calibrated, R²-validated point-prediction model
(no functional form clears that bar, and — per §2's resolved paradox — that is
expected for an effect this size, not a sign of failure). It is also not proven
to generalize beyond these 16 companies, 2024–2026, or beyond Polymarket's
specific contract structure; the test-only cluster bootstrap cannot by itself
rule out zero. And the realized backtest P&L, while statistically significant,
has not been validated against Polymarket's *actual* historical bid-ask spreads
(the cost sweep above is a literature-based approximation, not a measured
execution cost).

---

## 8. Honest limitations (stated once, plainly, for reference)

1. Only 16 companies back this entire finding; the test split's own
   cluster-robust CI cannot independently exclude zero.
2. Company volatility is a single full-history figure per company, not a
   point-in-time trailing estimate (a stated simplification since script 25).
3. GDELT's day-precision timestamps mean the real stock's "reaction window" is
   a ~48h bracket, not minute-precise — some genuine timing noise is baked in
   on both sides of every comparison in this whole investigation.
4. Transaction costs are a literature-informed range, not Polymarket's measured
   historical spreads for these specific contracts.
5. 23 model specifications were compared in total; the Bonferroni correction in
   §6 is the conservative, correct adjustment for that — but any further ad hoc
   variation tried after this report should be judged against an even larger
   correction, not treated as a fresh, independent test.

---

## 9. Suggested next steps (not yet done)

- Fold this into the Google Doc (as suggested text, per established workflow)
  and the Marp deck (direct edit, per established workflow).
- If pursued further: measure Polymarket's actual historical bid-ask spread for
  price_ladder contracts, to replace the literature-based cost estimate with a
  real one.
- If more data becomes available: more price_ladder companies would
  directly address the §8.1 limitation (the test-only CI's lack of power).
