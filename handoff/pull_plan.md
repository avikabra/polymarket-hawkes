# Full plan: from companies to the final result

Status marks: **Done** (built and run), **Agreed** (approved, not built), **Proposed** (waiting on
a decision). Open decisions are listed at the end, numbered D1 to D14, and each step that depends
on one names it.

## Dates used everywhere

| Period | Dates | Used for |
|---|---|---|
| Stock history | 2020-09-01 to 2026-10-30 (D8) | Stock characteristics only (beta needs 60 months, momentum 12) |
| Polymarket data | 2025-09-26 (first company trade) to 2026-10-30 | Contracts, trades, Polymarket block |
| Articles | 2025-09-26 to 2026-10-30 | Shocks, Z-score history |
| Shock use period | About 2025-10-26 to 2026-10-30 | Days that get a shock |
| Part two train | Shock start to about 2026-06-15 | Fit the prediction model |
| Part two validation | About 2026-06-16 to 2026-08-27 | Tune the prediction model |
| Part two test | 2026-08-28 to 2026-10-30 | Scored once, at the end |

The earlier model's data ended 2026-08-27, so the test months are dates no earlier result has
touched. There is no 2022-2024 period: Polymarket has no company contracts then.

---

# Part one: build the news shocks

## 1. Companies (Done)

1. The study covers 61 companies. Each is publicly traded, has a ticker of at least 3
   characters, and has at least one resolved Polymarket contract.

   | Company | Ticker | Company | Ticker | Company | Ticker |
   |---|---|---|---|---|---|
   | Adobe | ADBE | GameStop | GME | Pfizer | PFE |
   | Airbnb | ABNB | Alphabet | GOOGL | Qualcomm | QCOM |
   | Amazon | AMZN | HP | HPQ | Reddit | RDDT |
   | AMD | AMD | IBM | IBM | Rivian | RIVN |
   | American Express | AXP | Intel | INTC | Robinhood | HOOD |
   | Apple | AAPL | Intuit | INTU | Roblox | RBLX |
   | Arm | ARM | JPMorgan Chase | JPM | Salesforce | CRM |
   | Bank of America | BAC | Lockheed Martin | LMT | Snowflake | SNOW |
   | BlackRock | BLK | Lyft | LYFT | SpaceX | SPCX |
   | Broadcom | AVGO | McDonald's | MCD | Starbucks | SBUX |
   | Chevron | CVX | Merck | MRK | T-Mobile | TMUS |
   | Cloudflare | NET | Meta | META | Tesla | TSLA |
   | Coinbase | COIN | Microsoft | MSFT | TSMC | TSM |
   | Costco | COST | MicroStrategy | MSTR | Uber | UBER |
   | CrowdStrike | CRWD | Moderna | MRNA | UnitedHealth | UNH |
   | Datadog | DDOG | Netflix | NFLX | Walmart | WMT |
   | Dell | DELL | Nike | NKE | Wells Fargo | WFC |
   | Disney | DIS | Nvidia | NVDA | Workday | WDAY |
   | DoorDash | DASH | Oracle | ORCL | | |
   | Eli Lilly | LLY | Palantir | PLTR | | |
   | ExxonMobil | XOM | Palo Alto Networks | PANW | | |
   | | | PayPal | PYPL | | |

2. Each company has a list of names it appears under in the news: plain name, short names,
   subsidiaries, brands, products and shows. `config/companies.yaml` holds 4,428 names and 500
   context names, reviewed by hand. A context name (Siri, Marvel, Threads) is a real brand that
   also means something else, so it counts only in an article that also contains one of the
   company's ordinary names. Tickers are never names.
3. Sync the final list to Bouchet (the last 4 removals are local only).

## 2. Contracts (Done)

4. Pull every resolved Polymarket contract on these companies through 2026-10-31, found by the
   company's ticker tag. The first company trade is 2025-09-26.
5. Read each contract's type from Polymarket's tags, first match wins: earnings, KPI, market cap
   or IPO, barrier ladder (Hit Price), close ladder (Multi Strikes; a set of exclusive price
   ranges is a closing bucket), up or down. Contracts with none of these tags leave the data.
6. Keep only contracts whose price can change over a full day.
7. Treat each event as one contract group, with its markets as rungs.
8. Read each rung's strike from its label ("↑ $405", "$630", "<$240").
9. Read each rung's direction from the label, or from the question when the label is a bare price.
   Earnings contracts have no strike.
10. Remove contracts whose strikes changed meaning (Netflix's November 2025 split).
11. Check each ladder against its outcomes (monotone YES in a ladder, exactly one YES in a bucket
    set, close ladder matches the real close). Failures leave and are listed. 106 contracts failed
    the rules: 105 had no financial type tag, 1 had an unreadable strike.
12. Give each contract a start and end time in Eastern time. A barrier contract ends when it
    settles, if that comes first.
13. Keep the trade history of every contract with at least $1,000 traded, to the second, in
    log-odds.
14. Run every later result twice: contracts with $1,000+ traded, and the $10,000+ subset.

## 3. Articles (Done)

15. Find articles through GDELT's public files (not BigQuery) for every day a company has an open
    contract. GDELT dates articles to the day.
16. Keep an article when a company name appears in it as a whole word with exact capitalization.
17. Download each article's full text from the publisher on Bouchet (4 Slurm tasks, 1 connection
    per domain). Recheck the name in the extracted text; failures and articles without a name keep
    only url and status. The fetch finished on Bouchet (job 32323285).
18. Remove duplicate URLs here. Same-headline same-day duplicates are removed after matching
    (step 31).
19. Drop the 89,114 URLs from the old 2022-2024 period, which nothing uses (D12).

## 4. Embeddings (Agreed)

20. Embed each matched article with Qwen3-Embedding-4B on Bouchet: headline, lede, body, source and
    date together. The output is 2,560 numbers, scaled to length 1.
21. Embed only matched articles, after duplicate removal (step 31).

## 5. Matching articles to companies (Proposed: D1, D2)

22. The question is asked per article and company pair: is this article primarily about this
    company?
23. Filter first. A pair is asked only if a company name is in the headline or lede, or appears
    at least 3 times in lede and body. Context names count only beside an ordinary name. On the
    tuning sample the filter kept 200 of 202 true matches. On the current shards: 836,940 articles
    pass, giving about 930,977 questions (estimate about 1.2 million once the full fetch is
    scanned).
24. Ask Qwen3.5-4B with this system prompt, word for word:
    "You decide whether a news article is primarily about one company. The brands listed with the
    company belong to it, so an article about one of those brands is an article about the company,
    even when the text never mentions the company's own name. Answer yes if the company or anything
    it owns is a main subject of the article: its products, services, shows, games, subsidiaries,
    deals, staff moves, stock or earnings. There can be several main subjects. Answer no if it is
    only mentioned in passing: a place something was posted, sold or streamed while the story is
    about something else, one name in a long list, a person's past employer, or a different thing
    with the same name. Also answer no for shopping deal lists, roundups of many unrelated items,
    and stories about a person or a topic where the company's product is only the setting."
25. The user message holds the company, its names, the article (headline, then lede and body cut
    to 2,500 characters as in tuning, flagged if cut), and two counts: "Named in headline: yes/no. Mentions in text: N."
26. Output is yes or no, by JSON schema. Thinking off, temperature 0, vLLM offline batch, one L40S,
    prefix caching on, results written in resumable chunks. Prompt version v3. About 25
    questions per second, so about 13 hours.
27. Log per chunk: done, remaining, speed, time left, tokens, GPU memory, yes share, cut count,
    failures.
28. Run 1,000 pairs first to check speed and read answers.
29. Hand check: pass bar 98% for precision and recall, set in advance. You label 200 random
    articles across companies, blind to the model, including articles the filter dropped. On the
    test half of the tuning sample the prompt reached 89.8% precision (97.2% counting borderline
    cases right) and 89.8% recall, against Sonnet labels. That is below the bar (D1).
30. If it misses the bar, change the prompt, rerun step 28, and check a fresh 200.
31. After matching: strip text from articles with no match, remove same-headline same-day
    duplicates among matched articles (keep the longest body), write `data/news/matches.parquet`
    (article id, company, cut flag, model, prompt version), then embed (step 20).

## 6. Compute the news shock (Agreed)

**The idea.** Part of any article is predictable from what is already known about the company.
A large chipmaker on a strong run gets articles about AI chips and rallies. Kelly et al.
("The Inefficient Pricing of News", NBER w35093) show that this predictable part is already in
prices. The part nobody could have predicted, which they call pure news, is what moves prices
later. So for each company and day we subtract the expected article and keep the remainder:

  shock = today's news − the news expected from the company's characteristics

All characteristic definitions are JKP's (Jensen, Kelly and Pedersen), checked against their code.

**Notation**

32. k is a company, D is a day (Eastern time). An article's embedding e is a list of 2,560 numbers
    describing its meaning.
33. A Polymarket price p becomes log-odds ℓ = ln(p / (1 − p)), with p kept between 0.001 and 0.999.
34. Everything about the company uses data up to the close of D−1. Only the articles are from D.
35. A month is one calendar month, as in JKP, counted back from D−1.

**Step 1: the day's news**

36. Average the embeddings of k's articles on D: Ē(k,D) = (1/n) Σ e_a. An article about two
    companies counts for both. No article means no shock that day.
37. Standardize each of the 2,560 numbers (Kelly): E_j = (Ē_j − μ_j) / σ_j, where μ_j and σ_j are the
    mean and standard deviation over all earlier company-days. This puts every number on the same
    scale, so none dominates just because it varies more.

**Step 2: returns, the raw material**

38. Stock return on a day: r = P_today / P_yesterday − 1, with dividends included. Excess return:
    r − r_f, where r_f is the 3-month T-bill rate divided by 12 for a month, then by 21 for a day.
39. Polymarket return on a day. For each contract, Δℓ = ℓ(last trade today) − ℓ(last trade before).
    Flip the sign when YES pays if the stock falls, so up always means good for the stock. Leave out
    closing buckets, which have no single direction. Drop a change whose previous trade is over 14
    days old (JKP's stale-price rule). The company's Polymarket return r^PM is the dollar-weighted
    average of Δℓ across its contracts that traded that day. A log-odds change is Polymarket's
    version of a return.
40. Accounting numbers (JKP's timing): a report becomes usable 4 months after its period ends and
    expires after 18 months. Income items add up the last four quarters. Use whichever of the annual
    and quarterly figures is newer.

**Step 3: the eight characteristics, JKP definitions**

41. Beta: β_k = Cov(r_k − r_f, r_m − r_f) / Var(r_m − r_f), over the last 60 monthly returns (at least
    36), with the S&P 500 (SPY) as the market. How much the stock moves with the market.
42. Size: market cap, ME.
43. Book-to-market: BE / ME, with BE = shareholders' equity + deferred taxes − preferred stock. If
    equity is not reported, BE = assets − liabilities. BE ≤ 0 counts as missing (Dell, HP,
    McDonald's, Roblox and Starbucks today). Cheap versus expensive.
44. Profitability: (EBITDA − interest) / BE. Profit earned per dollar of equity.
45. Investment: A_now / A_one year ago − 1, with A = total assets. How fast the firm is growing.
46. Momentum: (1 + r_{t−11}) × … × (1 + r_{t−1}) − 1, the return over the past year skipping the latest
    month. Needs 12 months of history.
47. Volatility: the standard deviation of daily excess returns over the last month, at least 15 days.
    A month with 10 or more zero-return days counts as missing.
48. Illiquidity (Amihud): the average over six months of |r_day| / dollar volume_day × 10⁶, at least
    60 days. How far the price moves per $1 million traded.
49. Momentum, volatility and illiquidity also have a Polymarket version: the same formula with r^PM
    and Polymarket dollar volume (momentum adds the r^PM, since log-odds changes add). The two
    versions are blended after ranking (step 52):
      blended = (1 − w) × stock rank + w × Polymarket rank
      w = $ traded in k's Polymarket contracts / ($ in k's Polymarket contracts + $ traded in k's stock),
      both over that characteristic's window.
    Polymarket gets a say in proportion to the money traded there. Stock volume is billions a day
    against thousands on Polymarket, so w may come out close to 0. Rule, set before computing w: if
    w is below 1% for every company, blend 50/50 instead (decided, D4). When the Polymarket version
    is missing, blended = stock rank. Polymarket momentum needs 12 months of history (JKP's rule), so
    it exists only from late 2026; until then momentum is the stock's.
50. Profitability, book-to-market, investment, size and beta have no Polymarket version.
51. Industry: 16 yes/no indicators for our 17 industry groups.

Sources: Yahoo for prices, volume, the S&P 500 fund, the T-bill rate and financial statements;
companiesmarketcap for market cap, assets and liabilities; Polymarket trades from Section 2.

**Step 4: put characteristics on one scale**

52. Each day, rank the companies on each characteristic and rescale the rank r out of n to
    x = 2(r − 1)/(n − 1) − 1, which runs from −1 (lowest) to +1 (highest). Missing is 0, the middle.
    Only the order matters, so an extreme value cannot dominate.
53. The company's row S(k,D) has 25 numbers: a constant 1, the 8 characteristics and the 16 industry
    indicators.

**Step 5: the expected article and the shock**

54. The model: E(k,d) = S(k,d) β + u(k,d). It says a company's news is a straight-line function of
    its characteristics plus a surprise.
55. β holds the slopes: one per characteristic for each of the 2,560 numbers. Row j says how the
    typical article changes as characteristic j goes from lowest to highest.
56. Training data for day D: every company-day with an article in the month ending at D−1. Each row
    gives an input S(k,d) (characteristics, known before d) and an output E(k,d) (that day's news).
    No price reactions enter, so β never sees what part two predicts.
57. Training: least squares picks the β that makes the surprises in those rows as small as
    possible: β̂ = (SᵀS)⁻¹ SᵀE. A month holds about 500 rows against 25 numbers per slope set.
58. Applying it (the "test" for that day): the expected article for k on D is S(k,D) β̂, and the
    shock is u(k,D) = E(k,D) − S(k,D) β̂. Day D's rows are never in its own training month.
59. Roll forward one day and repeat, so every day has its own training month and is always out of
    sample. This is Kelly's monthly re-estimation, shifted one day so D is excluded (decided, D3).
    The first shock is about 2025-10-26, one month after the first company trade.
60. Consistency with part two: the procedure is identical on every day, in part two's train,
    validation and test periods alike. A test-period shock uses only the month before it, which may
    reach back into the train period; that is past data and holds no reactions. What part two must
    lock before scoring the test period: the names, the matching prompt, the characteristic
    definitions and the one-month window. As a check, also build shocks with β frozen at the end of
    part two's train period, and confirm part two's results hold under both.

**Step 6: link to contracts**

61. Attach u(k,D) to every contract of k open at the midnight after D with at least $1,000 traded.
62. Record the move that follows: y = ℓ(midnight + 24 hours) − ℓ(midnight).
63. Save `data/news/news_shocks.parquet`.

---

# Part two: do news shocks predict Polymarket moves? (Proposed: D9 to D11)

Kelly's second step asks whether pure news predicts the next return, then trades on it. Part two
asks the same of Polymarket: does u(k,D) predict how company k's contracts move in the 24 hours
after D?

**Target**

64. For each link (company k, day D, contract c): y = log-odds at the last trade before midnight
    after D + 24h − log-odds at the last trade before midnight after D. Both clipped.
65. Flip the sign if YES pays when the stock falls, so a positive y always means good for the
    stock.
66. Closing buckets have no single direction, so they leave the target, as in step 39.
67. Rungs of one ladder move together, so standard errors cluster by contract group and by day.

**Split**

68. Train, validation and test by date, as in the date table. Skip one day at each cutoff so no
    24-hour window crosses it.
69. Report results with and without contracts that span a cutoff.
70. Lock names, prompt, characteristics and the model before looking at any test reaction.
71. Tune on validation; also run leave-one-company-out on train plus validation as a check.
72. Score the test period once.

**Model (D9)**

73. Kelly's method, carried over: for each embedding coordinate j and day D, form a portfolio that
    holds each linked contract with weight u_j(k,D) and earns its y. Find weights w over these
    2,560 portfolios that maximize the Sharpe ratio (MSRR, regress 1 on the portfolio returns),
    with ridge shrinkage. The strategy then holds each contract with weight u(k,D)·w.
    Kelly uses a rolling 24-month window; we use the train period and pick the ridge strength on
    validation. The exact shrinkage and any dimension cut get confirmed against the paper before
    coding.
74. Baselines, built the same way:
    - Raw embeddings: E(k,D) in place of u (Kelly's 1.1 comparison).
    - Market state only: M(k,D) in place of u.
    - Constant: hold every linked contract with the same sign.

**Results**

75. For each model: out-of-sample Sharpe per trade, out-of-sample R² of y, and the share of moves
    with the right sign. Bootstrap confidence intervals by day.
76. Repeat for: $1,000+ and $10,000+ contracts; with and without contracts
    spanning cutoffs; each contract type separately.
77. Trading costs: Polymarket fees and spread are not in the trade data. Report results before
    costs and state that (D10).

**Final product**

78. `data/news/news_shocks.parquet`, the results tables from steps 75-76, and a
    short write-up for Link.
79. The thesis claim: if pure news predicts Polymarket moves better than raw news and market state,
    Polymarket prices news inefficiently, as Kelly finds for stocks.

---

## Open decisions

| # | Decision | My recommendation |
|---|---|---|
| D1 | Matching: 98% bar | Approved to run with Sections 1-5; the hand check decides |
| D2 | Run matching on all articles | Approved; 1,000-pair test running |
| D3 | β month ends at D−1 (step 59) | Decided |
| D4 | Weight w (step 49) | Decided: money share; 50/50 if w is below 1% for every company |
| D5 | Volatility and illiquidity added to FF6 (step 49) | Yes, as you asked |
| D6 | Pull Yahoo statements for book equity and profitability (steps 43-44) | Decided: yes |
| D7 | Keep JKP's 12-month history rule for momentum (step 49) | Decided: yes |
| D8 | Stock history from 2020-09-01? | Yes |
| D9 | Part two model: Kelly's MSRR (step 73)? | Yes |
| D10 | Report before costs only? | Yes, stated plainly |
| D11 | Split with test from 2026-08-28? | Yes |
| D12 | Drop the 89,114 old-period URLs and the 571,000 Instagram/Facebook-only URLs? | Yes |
| D13 | Push the commits so Link can pull them? | Your call |
| D14 | The old README plan compared LSTM, transformer and TCN models. Still in scope? | Drop; Kelly's method is linear |
