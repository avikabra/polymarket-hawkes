# Weeks 7-9 — Direction Pivot

**Source:** Advisor meeting — "Prof Kelly Meeting @ Office", 2026-08-28
**Codebase:** Polymarket News Shock Thesis (Direction 4)
**Authored:** 2026-08-29

---

## 1. Context — What Triggered This

An advisor meeting with Prof. Kelly on 2026-08-28 issued a hard pivot: a sharp narrowing of scope and a resequencing of the work plan. The current codebase (Direction 4) was built for the opposite approach — broad multi-category coverage and architecture racing — and its most recent work (Weeks 4-6) is exactly what the advisor now says to defer.

---

## 2. Advisor Directives (from the Meeting Notes)

1. **Narrow to one area** — likely market-information contracts tied to public equities. Drop the sports + politics + geopolitics triad.
2. **The real problem is matching** — connect a full news article to the exact binary contract it should affect. Full article body text is required; headlines and ledes are not sufficient.
3. **Do serious EDA on Polymarket log-odds before any text modeling** — which contracts are liquid, how often they trade, how log-odds move, whether demeaning and normalization clean the series.
4. **Use article metadata alongside text for matching:** time, company/ticker, topic, publication source, contract creation/resolution dates — narrow candidates before any LLM judgment.
5. **A small open-weight LLM is acceptable as a second-stage judge** after deterministic candidate filtering. Use sparingly; keep compute modest.
6. **Reuters is the preferred high-quality source.** Kelly can request Reuters feed access once the exact contracts and date range are known. Audit GDELT first to decide whether it suffices.
7. **Yale compute is available** (Kelly has PI access on clusters); access requests must be submitted by the researcher.
8. **Explicitly defer:** LSTM, Transformer, TCN, and cross-category comparisons — until full-text matching is proven clean and the liquid-market log-odds target is shown usable.
9. **Next meeting is a late-September data review.** Bring a short deck answering three questions: (a) What is the usable market sample? (b) What does a real Polymarket reaction look like? (c) Can I reliably match full articles to those contracts?

---

## 3. Current Codebase State vs. the Pivot

| Dimension | Advisor Wants | Codebase Currently Has |
|---|---|---|
| **Scope** | ONE public-equity / market-information area | Universe partitioned into `category=nba/nfl/politics` (broad triad); no public-equity path exists |
| **First priority** | Rigorous log-odds EDA and visuals | No EDA or visualization tooling exists at all |
| **Matching** | Metadata-first, layered, full body text | Single-category text-similarity; metadata is not the backbone |
| **Modeling** | Defer all architectures | Scripts 15-21 (Linear / LSTM / Transformer / TCN + hypotheses H1-H4) fully built — this is the now-deferred frontier |
| **Pipeline status** | — | All scripts 01-21 implemented but stalled at script 07 (BGE embeddings; `_chunks/` empty, FAISS index never built; nothing downstream 08-21 has output; `shock_embeddings.parquet` does not exist) |

**Note:** Most primitives survive the pivot — Gamma discovery, Goldsky trade pull, log-odds conversion, resampler, GDELT client, trafilatura body fetcher, and verifier scaffolding all remain valid. What changes is scope, sequencing, and the missing EDA layer.

---

## 3b. Feasibility Findings — Gamma Catalog Probe (2026-08-29)

A live enumeration of the Polymarket Gamma API was run to size the company-contract universe.

**Probe methodology and pitfalls.** Two naive probes badly undercounted due to (a) a ≥14-day duration filter that deleted short/monthly contracts, and (b) a ~2,100-offset pagination ceiling on the `/events?tag_id` and unfiltered `/markets` endpoints; the `/markets?q=` text-search silently ignores its query string. The correct method is **day-level slicing of the `/markets` endpoint (limit=100, iterate offset per day)**, which stays under the ceiling and yields complete per-day coverage.

**Catalog reality.** ~500k+ total markets all-time; ~82% are daily sports micro-markets. Genuine company contracts are ~0.5–1% of the catalog — still in the hundreds, real, and active in 2026.

**No daily stock-price series exist.** The recurring company-price contracts are MONTHLY: batches of ~50–150 strike markets per big-tech name per month (e.g. "Will NVDA close above $190 end of July?"), each 30–37 days in duration.

**Liquidity screening is now free.** `volumeNum` (lifetime USDC) is present directly on the market object, alongside `volume1wk` and `volume1mo` — so liquidity can be screened at discovery time without pulling Goldsky trades. This dissolves the chicken-and-egg problem noted earlier.

**Four company-contract families in the live catalog:**

| Family | Example | Volume | Notes |
|---|---|---|---|
| Monthly stock-price strikes | "AAPL close above $310 end of July?" | $5k–85k each, many strikes | Cleanest price-reaction target |
| AI-model leadership (monthly) | "Anthropic have the best AI model end of Aug?" | $500k–3.6M (highest vol) | Product/news-driven; not a price contract |
| Corporate events (one-off) | M&A / earnings beat / CEO exit / IPO valuation | $10k–12M | Classic discrete news shocks |
| MicroStrategy BTC series | "MSTR sells any Bitcoin by May 31?" | Up to $375M | Bitcoin-driven; not company news |

---

## 3c. Methodological Contributions (DUS Requirement)

The Director of Undergraduate Studies requires the thesis to contribute novel concepts or mathematical methods — applying off-the-shelf tools does not satisfy this bar. Two active threads are selected below. The pipeline plumbing must be instrumented to support them (exposing group structure, recording liquidity alongside reactions, etc.) and must not foreclose either thread by baking in architectural assumptions prematurely.

### Thread 1 — Article↔contract matching as embedding-space structure

Article-to-contract matching is formulated as a measurable structure in embedding space, driven jointly by characteristics of the company being evaluated and the contract description, with contract liquidity used as a sanity check on whether a claimed match corresponds to a real information event. This is the central methodological problem of the pivoted thesis. It must be a genuine method — not a FAISS-similarity lookup plus a verifier — with a formal account of when a match is warranted. **Status: direction agreed, not yet fully designed.**

### Thread 2 — Log-odds reaction model over the parent/child strike ladder

Monthly stock-price contracts are linked as a parent (company, expiry-month) with individual strikes as children. A single news shock moves the whole ladder jointly, and children are monotone by no-arbitrage: P(above $180) ≥ P(above $190). The reaction model must incorporate this joint, shape-constrained structure rather than treating each contract's reaction as an independent scalar. The goal is a model or formula that describes the ladder's collective log-odds response to a shared shock, exploiting cross-strike information rather than discarding it. **Status: explicitly research-in-progress — the formula is NOT to be locked prematurely.**

### Other identified novelty surfaces (parked)

On record but not active threads at this time:

- **Timestamp inverse problem** — infer true news-arrival time from the shape of the market reaction rather than assuming the article timestamp is correct.
- **Attribution under simultaneous overlapping shocks** — disentangle the contribution of each article when multiple shocks are co-incident in a short window.
- **Rigorous notion of news "surprise"** — a definition sharper than the linear purging residual (e.g., grounded in prior contract beliefs or implied volatility surface).
- **Impact-aware / contract-conditioned embeddings** — embedding representations that are explicitly trained to predict contract-level price reactions, not just semantic similarity.
- **Endogenous-liquidity selection bias** — liquidity is not randomly distributed; markets that attract volume may be systematically different from thin markets in ways that confound the reaction estimate.
- **Endogenous reaction-horizon estimation** — rather than fixing Δ (e.g., 6 hours), estimate the horizon from the data as the time at which the shock's effect has been fully incorporated.
- **Weak-signal evaluation methodology** — a protocol for assessing matching and reaction quality when ground-truth labels are sparse or absent.

---

## 4. Work Plan for Weeks 7-9 (Priority Order)

1. **Redefine the universe** — rewrite the scope of `01_discover_universe.py` with the following locked decisions:

   - **Scope: individual companies only (public + private); NO indices/ETFs/commodities.**
   - **Contract types IN: (a) monthly stock-price strike contracts, (b) one-off corporate-event contracts (M&A, earnings, CEO/exec changes, IPO valuations).** Private companies (OpenAI, SpaceX) enter only via the corporate-event family since they have no public stock strikes.
   - **Contract types OUT: AI-model-leadership product markets, MicroStrategy/BTC series, stock indices, commodities, crypto-token price markets, sports, politics/macro, and "will [person] say [word]" speech markets.**
   - **Discovery method: day-sliced `/markets` enumeration + a company-name dictionary + a classifier that applies the IN/OUT rules above.** Remove the old duration filter entirely.
   - **Liquidity: NO volume floor at discovery.** Record `volumeNum`, `volume1wk`, `volume1mo` on every contract; apply the liquidity cut LATER, after the log-odds EDA (per "decide the target after visuals"). Flag date-range as a tunable parameter (default: wide, e.g. 2024-01-01 → present, to accumulate enough monthly-strike + event observations).

   **Parent/child structure (adopted).** Monthly stock-price strike contracts are grouped under a parent header keyed by `(company, expiry-month)`; the individual strikes are children, each carrying a shared `group_id`. The matched article set attaches at the parent level and fans out to all children, enabling relative cross-strike response analysis — the substrate required for Thread 2. Corporate-event contracts remain standalone but carry a `company_id` so they can be grouped per-company later if needed. Every child record must retain its `group_id` throughout the universe definition and all downstream reaction-window plumbing, so the joint strike-ladder response can be assembled for a shared news shock.

2. **Build the EDA layer (new — the actual deliverable)** — a new script or notebook producing: distribution of 6-hour log-odds changes; share of zero-moves; trade frequency and volume per contract; before/after demean and normalize; event-time plots around known articles. The market-reaction target must be chosen only after seeing these results — do not trust last-trade Δ if inactivity manufactures zeros.

3. **Audit GDELT coverage for the new equity universe** (body-text percentage, timestamp quality, metadata completeness), then draft the Reuters request specifying exact date range, tickers/entities, full text, timestamps, headlines, ledes, and metadata fields.

4. **Refactor matching to metadata-first, layered** — ticker/entity/time/contract-date filters applied before embeddings; small open-weight LLM as second stage only; persist rationale and confidence score; flag uncertain matches for manual review. Note: the current `--llm` path uses Claude Haiku, whereas Kelly specified open-weight — this is an open decision requiring resolution.

5. **Freeze Weeks 4-6 (scripts 15-21)** — do not finish script 07 through training solely to race architectures. Park cleanly; may return after matching is validated.

6. **Request Yale cluster access now** (researcher submits independently) to unblock later compute requirements.

---

## 5. Open Decisions to Confirm

The following three items from the prior list are now **resolved**:

- **Contract universe — RESOLVED:** Individual companies (public + private); monthly stock-price strikes + one-off corporate-event contracts IN; AI-model leadership, MicroStrategy/BTC, indices, commodities, sports, politics/macro OUT.
- **Pivot mechanics — RESOLVED:** Refactor D4 in place (no hard-fork).
- **LLM judge — RESOLVED (partial):** Open-weight model per Kelly's directive; specific model choice still pending.

Genuinely open items remaining:

- **Exact date window:** Default of 2024-01-01 → present is a starting assumption; confirm once the EDA shows how many observations that yields per contract family.
- **Liquidity threshold:** Deferred to post-EDA. `volumeNum`, `volume1wk`, and `volume1mo` are recorded at discovery; the cut is applied after log-odds visuals are in hand.
- **Company-name dictionary source:** The discovery classifier requires a seed list of company names/tickers. Source (e.g. S&P 500 constituent file, hand-curated for private names) is not yet chosen.

---

## 6. Definition of Done for Weeks 7-9

A late-September data-review deck that answers Kelly's three questions, backed by: a defined liquid public-equity contract sample, log-odds reaction visuals, and worked examples demonstrating whether full-article-to-contract matching is clean.
