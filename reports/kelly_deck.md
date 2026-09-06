## Slide 1 — Company News Shocks in Polymarket

Late-September data review 
 Avi Kabra · Applied Mathematics Senior Thesis · Yale University 
 Do prediction-market prices re-price when company news lands — and can we measure it cleanly?

## Slide 2 — Roadmap

- Q1. What is the usable market sample? 

- Q2. What does a real Polymarket reaction look like? 

- Q3. Can we reliably match full articles to those contracts? 

- What changed since August · Next steps · Decisions & asks

## Slide 3 — Since August, the pivot is done

- Was: sports + politics + geopolitics; headline-only text; a preliminary null result. 

- Now: one area — individual-company contracts; full real trade history; a complete log-odds analysis. 

- Built the universe → pulled every trade → audited the news → tested matching directly.

## Slide 4 — Q1 — The usable sample: 6,928 contracts, 86 companies

- Individual companies only (public + a few private ladders). No sports, politics, crypto, or index markets. 

- Window: April 2024 – August 2026. 

- Two contract types: monthly price strike ladders + one-off corporate events . 
 
 

| Contract family | Contracts 

| Price ladders (monthly strikes) | 6,174 

| Corporate events (earnings, M&A, execs) | 470 

| Revenue ladders | 170 

| Valuation ladders (private cos.) | 110 

| Market-cap ladders | 4

## Slide 5 — Q1 — A liquid core, but concentrated

| Liquidity floor | Share of contracts 

| Traded at all | 93.6% 

| Over $1,000 volume | 70.4% 

| Over $10,000 volume | 21.0% 

| Top 500 markets | 62.6% of all volume 
 
 

- Total lifetime volume: $79M . 

- Clean set (≥ 200 trades and ≥ 10 active trading days): 473 contracts . 

- A real tradeable core exists; the thin tail is screened out before modelling.

![fig3_trade_frequency_volume_company.png](figures/fig3_trade_frequency_volume_company.png)

## Slide 6 — Q2 — A real reaction is mostly nothing, then a big jump

- Measured on 72.5M minute-by-minute observations from the liquid contracts. 
 
 

| Six-hour log-odds change | Value 

| Windows that are zero-move | 74.6% 

| Distribution mean | ≈ 0 

| Distribution std. dev. | 0.44 
 
 

- Thesis: most of the time the market does not trade, so it does not move — this is the central fact.

![fig1_delta_distribution_company.png](figures/fig1_delta_distribution_company.png)

![fig2_zero_move_share_company.png](figures/fig2_zero_move_share_company.png)

## Slide 7 — Q2 — When it moves, it moves a lot

| Non-zero six-hour move | Log-odds 

| Median | 0.41 

| 90th percentile | 1.66 

| 99th percentile | 5.17 
 
 

- Reference: 0.40 → 0.44 is +0.16 log-odds; a 0.41 move is a decisive probability swing. 

- Thesis: the reaction is real and economically large — it is just sparse.

## Slide 8 — Q2 — We will not fix the target on 6-hour last-trade changes

- Three-quarters of apparent "reactions" are inactivity, not genuine non-response. 

- Build and compare three target definitions: 
 
 

| # | Target definition | Rationale 

| 1 | Shorter window (1–2h) | less dead time 

| 2 | Event-/trade-conditioned | measure around real activity — most promising 

| 3 | Clean liquid set only | remove structural zeros 
 
 
- Final target is evidence-based — and yours to confirm.

## Slide 9 — Q3 — We find the news, but not cleanly — and we measured how far it gets us

- Free option (GDELT), tested directly on 40 real corporate events: 
 

| Test | Result | Verdict 

| Event coverage (±2 days) | 78% | partial 

| Primary journalism share | 1.2% | buried in noise 

| Body-text scrape yield | 69% | usable, biased 

| Market resolution vs. timestamp | 24 min vs. 1 day | ≈ 60× too coarse

![fig6_gdelt_validation_company.png](figures/fig6_gdelt_validation_company.png)

## Slide 10 — Q3 — Matching must be learned; the clean study needs a real feed

- Naive name-matching is ~5% correct on a major company → matching must be learned and validated. 

- Narrow first by company / ticker / time / contract dates → then a small model judges. 

- Now (free): build and validate the pipeline on GDELT + scraped text. 

- Final study: licensed newswire — for minute timestamps and paywalled full text. 

- Not a blocker: proceed now, add the clean feed for the precision pass.

## Slide 11 — What changed since the preliminary run

| | Preliminary (August) | This review 

| Universe | sports + politics + geo | one company-equity universe 

| Prices | partial, headline-timed | full real trade history 

| Zeros | 66% — cause unclear | 74.6% — explained (inactivity) 

| Matching | assumed workable | gap measured, not guessed 
 
 
- Thesis: the preliminary run showed where the data broke; this review fixes the measurement before touching models.

## Slide 12 — Next steps — measurement first, models later

- Build the matching pipeline on the free corpus; hand-audit a sample of matches. 

- Implement the three reaction targets; compare on the clean set. 

- Stand up Yale (Bouchet) compute; request the news feed for the precision pass. 

- Deferred, deliberately: LSTM / Transformer / TCN and cross-category comparisons — until clean matching and a usable target are proven.

## Slide 13 — Decisions made — and where I need you

| Decided this cycle 

| Explore all three reaction targets, then choose 

| Keep public equities + private valuation ladders (two panels) 

| Model on the liquid subset (volume > $10k → 1,452 contracts) 
 
 

| Where I need you 

| Approve / route the news-feed request (Reuters, or Yale library entitlement) 

| Confirm you will sponsor the Yale cluster account

## Slide 14 — Questions for Professor Kelly

- Reaction target: shorter window, event-conditioned, or clean-set-only — most credible as the primary estimand? 

- Inferential unit: the news event, the individual contract, or a two-way event × contract structure? 

- Scope: keep the private valuation ladders, or restrict to public equities? 

- News feed: request Reuters directly, or start from the library's existing entitlement?
