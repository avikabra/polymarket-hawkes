# Polymarket news shocks: the full pipeline

This document describes the whole project from the company list to the final result, step by step,
with what each step computes, why, and how it is built. Steps are numbered once across the whole
document. Everything heavy runs on Yale's Bouchet cluster; nothing heavy runs on a laptop.

## The question

Didisheim, Kelly, Pourmohammadi and Tian ("The Inefficient Pricing of News", NBER w35093) split
every news article about a company into two parts: the part anyone could have expected from what was
already known about the company, and the part nobody could have expected, which they call pure news.
They show that stock prices already contain the expected part, while pure news predicts returns for
the following month: a portfolio built on it earns a Sharpe ratio of 3.1, against 1.1 for the raw
articles.

This project asks the same question of Polymarket, the prediction market, using its contracts on
public companies ("Will Apple close above $250 on Friday?", "Will Nvidia beat earnings?"):

1. Does pure news about a company predict how its Polymarket contracts move in the next 24 hours?
2. Does Polymarket absorb the same news more slowly than the company's stock?
3. Where (thin or busy markets) and by whom (small or large trades) is the news absorbed?

## How the pieces fit

| Part | Sections | Output |
|---|---|---|
| Data | 1 Companies, 2 Contracts, 3 Articles | Company names, contracts with trade histories, article texts |
| Matching | 4 Matching, 5 Embeddings | Which articles are about which company, and each article's embedding |
| News shock | 6 | One pure-news vector per company and day |
| Prediction | 7 to 12 | The trading test, the stock comparison, the trade-size analysis |

Section 5 embeds only the articles that Section 4 matched.

## Dates

| Period | Dates | Used for |
|---|---|---|
| Stock history | 2020-09-01 to 2026-10-30 | Stock characteristics (beta needs 5 years, momentum 1 year) |
| Polymarket | 2025-09-26 (first company trade) to 2026-10-30 | Contracts, trades, Polymarket characteristics |
| Articles | 2025-09-26 to 2026-10-31 | Matching, embeddings, shocks |
| Shocks | About 2025-10-26 to 2026-10-29 | One month after the first trade, so the first month can be estimated |
| Train | 2025-10-26 to 2026-08-27 | First estimate of the trading model, not scored |
| Test | 2026-08-28 to 2026-10-29 | Scored once, after everything is locked |

There is no earlier training period: Polymarket had no company contracts before September 2025. The
test starts on 2026-08-28 because earlier work in this project used data up to 2026-08-27, so the
test months have never been looked at.

## Status

| Section | Status |
|---|---|
| 1 Companies | Done |
| 2 Contracts | Done |
| 3 Articles | Done |
| 4 Matching | Built; not yet run on Bouchet; test run next |
| 5 Embeddings | Waiting on matching |
| 6 News shock | Approved; not built |
| 7 to 12 Prediction | Approved; not built |

---

# Part one: data

## 1. Companies

1. **The 61 companies.** Each company meets three conditions: it is publicly traded, because every
   later measure needs a stock price; its ticker has at least 3 letters, because one- and two-letter
   tickers (V, C, MS) are also ordinary words; and it has at least one resolved Polymarket contract.

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

2. **Names.** An article about Instagram is news about Meta, so each company needs every name it
   appears under: its plain and short names, subsidiaries, brands, products and shows. The list
   started from Wikidata's subsidiary and brand records and was then reviewed by hand, company by
   company. It holds 4,428 names and 500 context names.
   - A **context name** is a real brand that also means something ordinary: Siri, Marvel, Threads,
     Model 3, Optimus. It counts only in an article that also contains one of the company's other
     names, so "Optimus" counts in a Tesla article but not in a Transformers review.
   - Tickers are never names, because they collide with words.
   - Examples. Apple: Apple, iPhone, MacBook Pro, AirPods, Apple TV, CarPlay, Beats by Dre (context:
     Siri, App Store, Macintosh, Shazam). Disney: Disney, ESPN, Hulu, Pixar, Star Wars, Marvel
     Studios (context: Marvel, ABC News, Avengers, The Simpsons). Costco: Costco, Kirkland Signature,
     Costco Food Court.
   - Known gap: MicroStrategy renamed itself Strategy, a word too common to search for alone, so its
     articles are probably undercounted.
3. **Industries.** Each company gets one of 17 GICS industry groups, assigned by hand from public
   listings (the official table is licensed). SpaceX takes the closest fit.

Built by `scripts/ingest/01_company_names.py`. Stored in `config/companies.yaml` and
`config/gics.yaml`, both synced to Bouchet.

## 2. Contracts

4. **Pull.** Pull every resolved Polymarket contract on the 61 companies through 2026-10-31.
   Polymarket tags each company contract with the company's ticker, so the tag identifies the
   company with no searching of titles. Only resolved contracts are pulled, because later steps use
   how each contract ended. 32,562 contracts (rungs) were pulled.
5. **Type.** Read each contract's type from Polymarket's own tags. When a contract carries several,
   the first match in this order wins:
   1. Earnings: will the company beat its quarterly estimate.
   2. KPI: will a reported business figure clear a threshold.
   3. Valuation: market cap or IPO value.
   4. Barrier ladder ("Hit Price"): will the stock touch a price before the end.
   5. Close ladder ("Multi Strikes"): where the stock closes at the end. A set of mutually exclusive
      price ranges is a closing bucket.
   6. Up or down.

   Contracts with none of these tags leave (6,473, such as Netflix Top-10 show markets), because
   they say nothing about the company's value.
6. **Length.** Keep only contracts open for more than a day, because the reaction measure is a
   24-hour change. 3,010 daily contracts and 513 contracts open under 24 hours leave.
7. **Groups.** Each event is one contract group and its markets are the rungs: a price ladder is one
   event with one market per strike.
8. **Strike and direction.** Read each rung's strike from its label ("↑ $405", "$630", "<$240"). Read
   its direction from the arrow or bound, or from the question when the label is a bare price ("Will
   Apple close above $250?"). Earnings contracts have no strike. 3 rungs had unreadable strikes and
   leave.
9. **Stock splits.** Remove rungs whose strikes changed meaning with a split. Netflix's 10-for-1 split
   in November 2025 changed its price; 24 rungs were cut short by it.
10. **Checks.** Each ladder is checked against its own outcomes: in an "above" ladder, YES at one
    strike requires YES at every lower strike; a set of buckets has exactly one YES; a close ladder's
    outcome matches the stock's real close. A failure means a strike or direction was misread, and
    the contract leaves with the failed check listed in the pull report.
11. **Times.** Each contract gets a start (when it began taking bets) and an end, in Eastern time. A
    barrier contract ends when it settles if a touch ends it early; every other contract ends at its
    scheduled time.
12. **Result.** 22,563 rungs kept in 2,536 groups:

    | Type | Groups | Rungs |
    |---|---|---|
    | Barrier ladder | 531 | 8,755 |
    | Close ladder | 594 | 7,400 |
    | Closing bucket | 463 | 5,094 |
    | Up or down | 608 | 608 |
    | KPI | 88 | 436 |
    | Earnings | 249 | 249 |
    | Valuation | 3 | 21 |

    Activity is concentrated: Meta, Alphabet, Microsoft, Apple, Tesla, Palantir, Amazon, Nvidia and
    Netflix have about 210 to 220 groups each; most other companies have under 10.
13. **Trades.** Pull every trade of every kept contract from Polymarket's public trade API, to the
    second. Each trade records price, size in dollars (USDC) and side (buy or sell). Prices are
    stored as probabilities and as log-odds, ℓ = ln(p / (1 − p)), with p held between 0.001 and
    0.999 so that 0 and 1 stay finite. Result: 832,257 trades worth $51.3 million, from 2025-09-26 to
    2026-10-30.
14. **Liquidity sets.** Every later result runs twice: on contracts with at least $1,000 traded, and
    on the subset with at least $10,000. The second set is smaller and its prices react faster, so
    comparing the two shows whether results depend on liquidity.

Built by `scripts/ingest/02_pull_contracts.py` (contracts, checks, pull report),
`03_pull_trades.py` and `03b_daily_volume.py`. Stored in `data/polymarket/` on Bouchet.

## 3. Articles

15. **Find articles.** GDELT is a free database of news articles worldwide. For each article it
    records the URL, date and source, plus the organizations and names that GDELT's own software
    found in the text when it crawled the page. Read GDELT's public files (one per 15 minutes) for
    every day a company has an open contract, keeping only web news (GDELT's collection 1). GDELT
    dates articles to the day, so no time within a day is used anywhere in the project. The pull
    scanned 42,522,203 GDELT records from 2025-09-26 to 2026-10-31.
16. **First name filter, on GDELT's record only.** Keep an article for a company when one of its
    names (step 2, context names excluded) appears as a whole word with exact capitalization in
    GDELT's organizations field or its all-names field, on a day the company has an open contract.
    "Apple" does not match "apple" or "Applebee's". This filter reads only what GDELT recorded: it
    never reads the URL and fetches nothing. It kept 5,004,614 (URL, company) rows, which is
    4,296,455 distinct URLs.
17. **Download the text.** GDELT stores no text, so every URL that passes step 16 is downloaded in
    full from the publisher; there is no cheaper first pass. On Bouchet, 4 parallel jobs each take a
    quarter of the URLs (split by a hash of the URL), with one connection per website at a time, 24
    connections per job, and a 20-second timeout. A page over 5 MB is dropped after it downloads. The
    text is extracted from the page's HTML in separate worker processes, so a page that crashes or
    hangs the extractor (30-second limit) loses only itself. Each block of 500 URLs is saved as one
    file, which is also the point a stopped job resumes from. 4,385,569 URLs were downloaded (this
    includes about 89,000 from an earlier 2022-2024 pull that nothing now uses), and 3,930,740
    returned the page.
18. **Second name filter, on the extracted text.** Right after extraction, look for the names of the
    companies step 16 flagged for that URL in the page title and the extracted text. Pages that
    failed and pages without a name keep only their URL and a status, so their text never piles up
    on disk. 3,484,923 articles passed: 3,446,368 in the contract period and 38,555 from the
    2022-2024 pull.
19. **Duplicates.** Remove repeated URLs here. Articles with the same headline on the same day are
    removed after matching (step 34), among matched articles only.
20. **Result.** The download finished on Bouchet in two runs (the first stopped at its 23-hour limit,
    the second resumed and finished), leaving 8,843 files and 3,446,368 contract-period articles with
    text. Matching (step 22) skips the 2022-2024 rows and Instagram and Facebook pages, which leaves
    3,314,425 articles that name at least one company.

Built by `scripts/ingest/04_pull_gdelt.py` and `05_fetch_articles.py`, run as Slurm jobs. Stored in
`data/news/fetched/` on Bouchet.

---

# Part two: matching and embedding

## 4. Matching articles to companies

A name in an article does not make the article about the company: Apple appears in thousands of
stories about apps, phones in films, or someone's former employer. Matching reads each article and
decides which of the 61 companies, if any, it is about.

21. **The question.** Ask one question per article: which of the 61 companies is this article
    primarily about? The answer is a list of companies, which can hold several companies or none.
22. **Which articles are asked.** Every downloaded article with text in which at least one company's
    name appears. Nothing else decides whether an article is asked: no count, no position in the
    article. Two kinds of rows are skipped because no later step uses them: rows from GDELT's
    2022-2024 pull, and Instagram and Facebook pages. An article stored in more than one file is
    asked once, from its last copy.
23. **Names found.** A name counts when it appears as a whole word with exact capitalization in the
    headline, lede or body. A context name (a real brand that also means something else)
    counts only when a plain name of the same company also appears. For each
    company named in the article, the scan records the names found, how often they appear in the
    headline, and how often in the lede and body.
24. **Finding the names.** A CPU job reads the article files in two passes: the first finds each
    article's last copy, the second records the names found and their counts (step 23), the
    headline, and the lede and body cut to their first 2,500 characters, with a flag when cut. It
    runs once on CPUs so the GPU spends its time only on answering, and it fixes the list and order
    of articles that the GPU jobs resume from (step 28). It writes in blocks of 20,000 articles, so
    memory never holds more than one block, and uses 16 CPUs and 8 GB of memory for at most 3 hours.
25. **The model.** Qwen3.5-4B, an open language model, answers each question. It runs on one GPU on
    Bouchet with vLLM in batch mode. A fixed answer format, set per article, allows only the
    companies named in that article, exactly as listed, or an empty list for none; a name repeated
    in an answer counts once. Temperature is 0, so the same question always gets the same answer,
    and the model does no step-by-step thinking.
26. **The instructions** given before every question, word for word:

    > You decide which companies a news article is primarily about. The message lists the
    > companies whose names appear in the article, with the names found and how often they
    > appear in the headline and in the text; choose only from that list. A brand that belongs
    > to a company counts as the company. A company counts only if it, or something it owns, is
    > what the article is about: the headline or most of the text concerns its products,
    > services, shows, games, subsidiaries, deals, staff moves, stock or earnings. There can be
    > several such companies, or none. A company does not count when it is mentioned in passing
    > in a story about something else: a place something was posted, sold or streamed, a source
    > of a quote or a figure, one name in a list, a person's past or present employer, or a
    > different thing with the same name (a town, a word, a person). Obituaries, shopping deal
    > lists, roundups of many unrelated items, and stories about a person or a topic where a
    > company's product is only the setting count for no company. Use the counts as evidence: a
    > company named once or twice in a story about something else is a passing mention. When in
    > doubt, leave the company out. Answer with the company names exactly as listed; an empty
    > list means none.

27. **The question itself**, for an article naming Apple:

    ```
    Company names in this article:
    - Apple (as Apple, iPhone): 1 in the headline, 4 in the text
    Headline: <headline>
    Text: <lede and body, first 2,500 characters>

    Which of the listed companies is this article primarily about, if any?
    ```

    Each company named in the article gets one line, with up to six of the names found. If the
    whole question still exceeds 4,096 tokens, the text is cut further and flagged.
28. **Running in pieces.** Articles run in blocks of 2,000, and each finished block is saved, so a
    stopped job restarts from the first missing block. Memory holds the model and one block. Each
    job takes one GPU, 4 CPUs and 16 GB of memory for at most 6 hours, and hands the GPU back when
    it ends; the next job is submitted only after the last one has finished. After each block the
    log records articles done and left, speed, time left, tokens read and written, GPU memory, the
    share of articles matched to at least one company, the number of cut texts, and failures.
    Failed articles are saved and asked again in a separate pass.
29. **Test run, then full run.** 1,000 random articles run first, to measure speed and to read
    sample answers. The full run starts only after you have seen the test, with its expected GPU
    hours stated beforehand.
30. **Hand check sample.** Draw 200 articles for you to label, without seeing the model's answers:
    - 100 the model matched to at least one company, spread across companies by taking turns over
      each article's least common matched company;
    - 100 the model matched to no company.

    Each article carries a weight equal to how many articles its group stands for, so the scores
    describe every asked article, not only the sample. The labelling sheet shows the headline,
    source, date and text, and lists all 61 companies as checkboxes for each article.
31. **Hand check scores.** Articles whose main subject is a show, film or game (its cast, plot,
    release or reception) are left out of both scores, because whether they are news about the
    company that owns the title is ambiguous; they are still matched. The labelling sheet has a
    "show story" box for this. Precision is the share of the model's matches that you marked right.
    Recall is the share of your marked companies that the model found. Both are weighted (step 30),
    with 95% intervals from 10,000 bootstrap draws. The bar is 95% on both, set before seeing the
    hand-check results. If either misses it, the instructions change, the test run repeats, and a fresh 200 is
    drawn.
32. **Matches.** Each company in an answer becomes one match: article, company, cut flag, model and
    instruction version (v5).
33. **Clean up.** Articles with no match keep only their URL and status.
34. **Same-story duplicates.** Among matched articles of the same company, articles with the same
    headline on the same day are one story; the one with the longest text stays.

Built by `src/ingest/company_map.py` (instructions, names found, question), `scripts/ingest/
08_map_companies.py` (finding the names, test run, full run, retry, build of the matches) and
`09_hand_check.py` (sample and scores), run by `scripts/bouchet/ingest_08_scan.sbatch` and
`ingest_08_map.sbatch`. Output: `data/news/matches.parquet`.

## 5. Embeddings

An embedding turns a text into a list of numbers so that texts with similar meaning get similar
lists. It is what lets news be measured and compared.

35. **Model.** Qwen3-Embedding-4B, an open model that reads long texts in many languages. Each
    article becomes 2,560 numbers, scaled so the list has length 1.
36. **Text.** The headline, lede, body, source and date are embedded together, up to 8,192 tokens.
37. **Which articles.** Only matched articles, after duplicate removal (step 34).
38. **Run.** On one L40S GPU on Bouchet, in batches of 8, saved in pieces so a stopped job resumes.

Built by `scripts/ingest/07_embed.py`, run by `scripts/bouchet/ingest_07_embed.sbatch`.

---

# Part three: the news shock

## 6. Compute the news shock

**The idea.** Part of any article is predictable from what is already known about the company. A
large chipmaker on a strong run gets articles about AI chips and rallies. Kelly et al. show that this
predictable part is already in prices, and that the part nobody could have predicted moves prices
later. So for each company and day:

  shock = today's news − the news expected from the company's characteristics

Every characteristic uses the exact definition of Jensen, Kelly and Pedersen (JKP), checked against
their published code (github.com/bkelly-lab/ReplicationCrisis). Where our free data lacks an input JKP
uses, JKP's own fallback order applies; where every input is missing, the value is missing, as in JKP.

**Notation**

39. k is a company and D is a day (Eastern time). e is an article's embedding (step 35).
40. ℓ = ln(p / (1 − p)) is a price in log-odds, with p held between 0.001 and 0.999.
41. Everything about the company uses data up to the close of D−1. Only the articles are from D.
42. A month is one calendar month, as in JKP, counted back from D−1. JKP computes at month-ends; we
    compute the same formulas every day, with each window ending at D−1.

**Step 1: the day's news**

43. Average the embeddings of k's articles on D: Ē(k,D) = (1/n) Σ e_a. An article matched to two
    companies counts for both. A company with no article that day has no shock that day.
44. Standardize each of the 2,560 numbers, as Kelly does: E_j = (Ē_j − μ_j) / σ_j, where μ_j and σ_j
    are the mean and standard deviation over all earlier company-days. This puts every number on the
    same scale, so none dominates just because it varies more.

**Step 2: returns, the raw material**

45. **Stock return:** r = P_today / P_yesterday − 1, with dividends included. Excess return: r − r_f,
    where r_f is the 3-month T-bill rate divided by 12 for a month, and then by 21 for a day. JKP uses
    the 1-month bill; the 3-month bill is the closest free series.
46. **Stock dollar volume** on a day: close × shares traded.
47. **Polymarket return.** For each contract, Δℓ = ℓ(last trade of the day) − ℓ(previous last
    trade). Flip the sign when YES pays if the stock falls, so up always means good for the stock.
    Leave out closing buckets, which have no single direction. Drop a change whose previous trade is
    more than 14 days old (JKP's stale-price rule). The company's Polymarket return r^PM is the
    dollar-weighted average of Δℓ across its contracts that traded that day; a day with no trade is
    missing. A change in log-odds is Polymarket's version of a return.
48. **Polymarket dollar volume** on a day: the dollars traded across the company's contracts.
49. **Accounting timing (JKP):** a report becomes usable 4 months after its period ends, and expires
    after 18 months. Income items add up the last four quarters. Use whichever of the annual and
    quarterly figures is newer. TSMC reports in Taiwan dollars; its figures are converted to US dollars
    at the exchange rate on the report's period-end date, so its ratios compare with the other
    companies. Neither data source keeps first-reported versions, so later
    restatements cannot be excluded.

**Step 3: the eight characteristics, JKP definitions**

50. **Beta:** β_k = Cov(r_k − r_f, r_m − r_f) / Var(r_m − r_f), over the last 60 monthly returns (at
    least 36), with the S&P 500 fund (SPY) as the market. Monthly excess returns are trimmed at the
    0.1% and 99.9% points across companies, and months with a zero return are left out. How much the
    stock moves with the market.
51. **Size:** market cap, ME: the latest weekly value on or before D−1, scaled by the stock's price
    change since that week.
52. **Book-to-market:** BE / ME. BE = shareholders' equity + deferred taxes − preferred stock. If
    shareholders' equity is not reported, use common equity + preferred stock, then total assets −
    total liabilities. Missing deferred taxes or preferred stock count as 0. BE of 0 or less is
    missing; Dell, HP, McDonald's, Roblox and Starbucks have negative BE today. Cheap versus
    expensive.
53. **Profitability:** (EBITDA − interest expense) / BE. EBITDA is the reported figure, or revenue −
    operating expenses, or gross profit − SG&A, whichever comes first. Profit earned per dollar of
    equity.
54. **Investment:** A_now / A_one year earlier − 1, with A = total assets. How fast the firm grows.
55. **Momentum:** (1 + r_{t−11}) × … × (1 + r_{t−1}) − 1, the past year's return skipping the latest
    month. Needs 12 months of history.
56. **Volatility:** the standard deviation of daily excess returns over the last month, at least 15
    days. A month with 10 or more zero-return days is missing.
57. **Illiquidity (Amihud):** the six-month average of |r_day| / dollar volume_day × 10⁶, at least 60
    days. How far the price moves per $1 million traded.
58. **Polymarket versions.** Momentum, volatility and illiquidity also get a Polymarket version: the
    same formula with r^PM and Polymarket dollar volume (momentum adds the r^PM, because log-odds
    changes add). Each Polymarket version is its own characteristic, next to the stock version, so
    each gets its own slope in β (step 64). The slopes say how much each version shapes the expected
    article, set by last month's articles (step 65), with no weight chosen by hand. If the
    Polymarket version is missing, it is 0 (step 61). Polymarket momentum needs 12 months of history
    (JKP's rule), so it exists only from late 2026; until then its column is dropped, as an empty
    industry is (step 66).

    **Combined metric.** After β̂ is solved on day D (step 66), each pair gets one combined value.
    The weight on the Polymarket version is the length of its slope row against the stock version's:

      w = |β̂ Polymarket| / (|β̂ stock| + |β̂ Polymarket|)
      combined = (1 − w) × stock rank + w × Polymarket rank

    |β̂| is the length of the 2,560 slopes, i.e. how far the typical article shifts as that version
    goes from lowest to highest. The combined value is reported for each company and day; the shock
    itself uses both versions directly.
59. Size, beta, book-to-market, profitability and investment have no Polymarket version.
60. **Industry:** 16 yes/no indicators for our 17 industry groups (step 3).

**Step 4: one scale**

61. Each day, rank the companies on each characteristic and rescale rank r out of n to
    x = 2(r − 1)/(n − 1) − 1, which runs from −1 (lowest) to +1 (highest). Missing is 0, the middle.
    Only the order matters, so an extreme value cannot dominate. Ties share the average rank.
62. The company's row S(k,D) has 28 numbers: a constant 1, the 8 stock characteristics, the 3
    Polymarket versions (step 58) and the 16 industry
    indicators.

**Step 5: the expected article and the shock**

63. **The model:** E(k,d) = S(k,d) β + u(k,d). A company's news is a straight-line function of its
    characteristics plus a surprise u.
64. β holds the slopes: one per characteristic for each of the 2,560 numbers. Row j says how the
    typical article changes as characteristic j goes from lowest to highest.
65. **Data used for day D:** every company-day with an article in the month ending at D−1, about 500
    rows. Each row gives S(k,d), known before that day, and E(k,d), that day's news. No price
    reaction enters, so β never sees what Part four predicts.
66. **Solving for β:** least squares picks the β that makes the surprises on those rows as small as
    possible, β̂ = (SᵀS)⁻¹ SᵀE. This is solving an equation, with nothing to tune. An industry with no
    rows that month is dropped from that day's equation.
67. **The shock:** the expected article for k on D is S(k,D) β̂, and the shock is
    u(k,D) = E(k,D) − S(k,D) β̂. Day D's own rows are never in its month, so every shock is out of
    sample.
68. **Every day:** move forward one day and solve again. This is Kelly's monthly re-estimation,
    shifted one day so that D is excluded. The first shock is about 2025-10-26.
69. **Lock before the test:** the names, the matching instructions, the characteristic definitions and
    the one-month window are fixed before any test-period result is looked at. As a check, shocks are
    also built with β frozen at the end of the train period, and Part four is repeated with them.

**Data for this section, pulled on Bouchet**

70. Yahoo Finance: daily close, adjusted close and volume for the 61 stocks and SPY, the daily
    3-month T-bill rate, and the daily Taiwan dollar to US dollar rate (for TSMC), from 2020-09-01.
71. Yahoo Finance: annual and quarterly statements for the 61 companies: revenue, EBITDA, operating
    expenses, gross profit, SG&A, interest expense, shareholders' equity, common equity, preferred
    stock, deferred taxes, total assets and total liabilities. A coverage report lists which fields
    each company has.
72. companiesmarketcap.com, already stored: weekly market cap, and quarterly total assets and total
    liabilities with long history. Only points dated at a period end are used.
73. Polymarket trades from step 13.

Output: `data/news/news_shocks.parquet`, one row per company and day: the shock u, the raw news E,
the predictable news S β̂, and the characteristic row S.

---

# Part four: prediction

**The question.** Does a company's pure news on day D predict how its Polymarket contracts move over
the next 24 hours, and how does that compare with the stock? This follows Kelly's Section 4 ("The
MSRR Approach"), with a day in place of his month.

## 7. Reaction y

74. **Polymarket reaction.** y(k,D) is company k's Polymarket return over the 24 hours after D. For
    each contract, Δℓ = ℓ(last trade before midnight + 24 hours) − ℓ(last trade before midnight), with
    the sign flipped when YES pays if the stock falls. y > 0 means the market moved toward good news
    for the stock.
75. **Contracts that count:** open at the midnight after D, at least $1,000 traded through D, and at
    least one trade in the 24 hours. Closing buckets stay out. A contract that resolves inside the 24
    hours counts with its last trade before resolution.
76. y(k,D) = the dollar-weighted average of Δℓ across those contracts, pooled together. Each
    contract's weight is the dollars traded in it on day D, the day before the 24 hours, so the weights
    are known at midnight; a contract with no trade on D has weight 0. No contract counted means y is
    missing. One y per company-day, as Kelly has one return per stock-month; averaging a ladder's
    rungs avoids counting one bet many times.
77. **Money version:** the same weighted average (step 76) of (p′ − p) / p, the return on $1 placed on the
    good-news side (YES on an "above" contract, NO on a "below" one) at the midnight price and sold 24
    hours later.
78. **Stock version:** y^S(k,D) = the stock's return from the last close on or before D to the close
    of the next trading day. Used only when the next calendar day is a trading day, so both windows
    cover the same day.

**Standardized reaction ξ and its stock-implied part**

A contract on a stock is a digital option on it, so the stock's own move changes the contract's
price by a computable amount, and a log-odds change means different things near 0, near 1 and
near expiry. ξ puts every contract's move on one scale; ξ̂ is the part the stock's move forces.

78a. **Volatility.** σ(k,D) = the exponentially weighted standard deviation of the stock's daily log
     returns through D, half-life 20 trading days (10 and 60 as checks), in annual units (× √252).
78b. **Time left.** τ = NYSE trading time from a moment to the contract's scheduled end, in years of
     252 sessions, counting a session in progress by its share of 6.5 hours left. Δt = τ0 − τ1, the
     trading time inside the window; a window with Δt = 0 (weekend) gives no ξ.
78c. **ξ for one contract.** z = Φ⁻¹(p), p the last trade before the time, clipped as in step 13
     ("below" close rungs use 1 − p); for a barrier contract before its touch z = Φ⁻¹(1 − p/2). A
     barrier resolves on any 1-minute high or low in regular hours, close to continuous monitoring
     in trading time; the 13 "hit … before 2026" Netflix rungs filed as a close ladder are barriers.
     ξ_c = ± (z1·√τ1 − z0·√τ0) / √Δt, with the sign set so ξ > 0 is good news for the stock
     (− for an up-barrier). For a fairly priced close contract ξ_c is exactly a standard normal
     draw, whatever its price, strike or expiry. Contracts that settle inside the window drop out.
78d. **ξ̂ for one contract.** The same formula with the model price in place of p: Φ(d),
     d = [ln(S/K) − σ²τ/2] / (σ√τ), for a close contract, and the first-passage probability of the
     stock reaching K before the end for a barrier contract, at the stock prices S0 and S1 of step 78.
     For a close-above contract ξ̂_c reduces to the stock's standardized return,
     [ln(S1/S0) + σ²Δt/2] / (σ√Δt), the same for every strike and expiry.
78e. **Company targets.** y_ξ(k,D), ξ̂(k,D) = weighted averages of ξ_c and ξ̂_c with the weights of
     step 76, over contracts with a strike (close and barrier ladders); contracts without one
     (up-or-down, KPI, earnings, valuation) drop out of these and stay in y. The leftover is
     m_ξ = y_ξ − ξ̂: the part of Polymarket's reaction the stock's move does not explain. y_ξ is the
     headline reaction. In log-odds, y^imp averages L(S1, τ1) − L(S0, τ0) of the model price, and
     m = y − y^imp; these and y_money form the robustness rows.
78f. **Controls.** r̃_D and r̃_{D−1}, the stock's standardized returns on days D and D−1 (log return
     / (σ/√252)); and the starting gap g0 = the weighted average of (z_c(M) − ẑ_c(M))·√τ0/√Δt, where
     ẑ_c is Φ⁻¹ of the model price at the stock's last close before M.
78g. **Day definition.** Main: the midnight day above. Switch (option A): both the contract and the
     stock windows run from the 4 p.m. close on trading day D to the close on the next trading day,
     and the news is the articles dated D−1. GDELT dates articles only to the day, so it cannot split
     news at 4 p.m.; articles dated D−1 are all published before the window opens.

## 8. News shock

79. The predictor is u(k,D) from Section 6.
80. Two comparison predictors, as in Kelly's Figure 4: raw news E(k,D), and predictable news
    S(k,D) β̂. Since E = S β̂ + u, the three split each article into what was known and what was new.
81. A company-day enters only if it has both a shock and a y.

## 9. Split

82. **Train:** 2025-10-26 to 2026-08-27. The first estimate of the model uses all of it; nothing here
    is scored.
83. **Test:** 2026-08-28 to 2026-10-29, the last day with a full 24 hours after it. The model is
    re-estimated each day on all earlier days, so every test prediction uses only the past.
84. Nothing in the test period is looked at until every choice in Sections 1 to 11 is locked. It is
    scored once.
85. The model used on day D uses only company-days whose 24 hours have passed by the end of D, which
    means days up to D−1.
85a. **Diagnostics, training days only.** In bins of price and days left: mean ξ (near 0 if the
     contracts are fairly priced), mean ξ² (equals (true σ / priced σ)², so above 1 means Polymarket
     moves more than its prices imply), and the slope of ξ on ξ̂. They are read, and the half-life,
     the day definition and any bins to drop are locked, before step 84's test.

## 10. Fit

86. **Portfolio weights.** On day D, give company k the weight w(k,D) = u(k,D) · b, where b is a list
    of 2,560 numbers. Each coordinate j is a small strategy ("bet on companies whose news scores high
    on j") with daily return F_j(D) = Σ_k u_j(k,D) y(k,D). b blends the 2,560 strategies into the one
    with the highest Sharpe ratio. This is Kelly's maximum Sharpe ratio regression (MSRR).
87. **Solving for b:** minimize Σ_D (1 − b·F(D))² + λ b·b over the days before D, which gives
    b̂ = (FᵀF + λI)⁻¹ Fᵀ1. The first term is Kelly's objective, whose solution is the
    maximum-Sharpe blend. The second term (the ridge penalty) shrinks b toward 0, needed because
    there are 2,560 coordinates and only a few hundred days.
88. **Choosing λ** inside the training days by leave-one-out, as Kelly does: leave out one day, solve
    on the rest, check the left-out day, repeat for every day, and keep the λ with the best average.
89. **Every day:** solve again on all earlier days and apply b̂ to the next day's shocks.
90. **Comparisons:** repeat steps 86 to 89 with raw news E and with predictable news S β̂ in place
    of u.
91. **Check (Kelly's Section 6):** predict y directly by ridge regression, ŷ(k,D) = u(k,D) · c, then
    bet on the companies with the highest predicted y and against the lowest.

## 11. Score

92. **The trade.** At the midnight after D, for each company with news: if w(k,D) > 0, put w(k,D)
    dollars on the good-news side of its contracts; if w(k,D) < 0, put |w(k,D)| dollars on the
    bad-news side. Sell 24 hours later. The day's profit is R(D) = Σ_k w(k,D) y(k,D).
93. **Sharpe ratio** = average daily profit / standard deviation of daily profit: profit per unit of
    risk. 0 means no edge. Reported per day, in money (step 77, what a trader earns) and in log-odds
    (step 74).
94. **For the check in step 91:** R²_OOS = 1 − Σ(y − ŷ)² / Σ y², the share of the moves predicted,
    compared with predicting no move.
95. **Presentation, as in Kelly et al. Figure 4:** the out-of-sample Sharpe ratios on the test days
    of the news-shock (u), raw-news (E) and predictable-news (S β̂) strategies, side by side, in
    money (step 77) and in log-odds (step 74), each number labelled with its unit. Kelly et al.
    report Sharpe ratios as point values; their intervals and t-statistics are on alphas.
95a. **The reaction regressions.** The news enters as one number per company-day: ŝ(k,D), the
     out-of-sample ridge prediction of y_ξ from u (step 91). On test days, for each target T in
     y_ξ, ξ̂, m_ξ: T = α_D + β·ŝ + δ1·r̃_D + δ2·r̃_{D−1} + δ3·g0 + e, with day fixed effects α_D and
     errors clustered by company (by day as a check). β on y_ξ equals β on ξ̂ plus β on m_ξ. Beside
     them: y_ξ = α_D + β·ŝ + γ·ξ̂ + δ'X + e with γ free. A nonzero β on m_ξ, or with γ free, says the
     news moves Polymarket at a given stock move; it is read only where step 85a finds mean ξ² near
     1. Intervals: 10,000 resamples of test days through the whole pipeline, σ included. For the
     strategy, u is also residualized on r̃_D and r̃_{D−1} using earlier days only, and both versions
     are reported.
96. **Repeat for:** contracts with $10,000+ traded; shocks with β frozen at the end of training
    (step 69); each contract type alone. All numbers are before trading costs, which are not in the
    data.

**Comparison with the stock market**

97. Run steps 86 to 93 with the stock return y^S (step 78) in place of y, on the same company-days.
    This is Kelly's test on the same news and days.
98. Compare the two Sharpe ratios. A higher Sharpe on Polymarket means Polymarket absorbs the same
    news more slowly than the stock market.
99. **How far Polymarket follows the stock:** across company-days, y = a + c·y^S. c is the log-odds
    move per 1% stock move; R² is the share of Polymarket's move the stock explains. Repeated with
    y_ξ on the stock's standardized return r̃_D (step 78f), where an efficient close contract has
    c = 1.
100. **Pure news: one strategy, two markets.** Each test day, the pure-news strategy decides which
     companies to bet on and how much (step 92). Apply those same bets to the stock on the same days.
     Both give a daily return per dollar (steps 77 and 78), so the two are directly comparable.
101. **Regress Polymarket's daily return on the stock's:** Polymarket return = a + c × stock return.
     c asks whether, when pure news pays off in the stock, it also pays off on Polymarket: near 1,
     Polymarket mirrors the stock; near 0, it reacts on its own. a is Polymarket's alpha over the
     stock, the profit the stock's reaction does not explain. A positive a means Polymarket misprices
     pure news in a way the stock does not.
102. **Precision:** a and c with 95% intervals, by resampling test days 10,000 times.

**Trade size**

103. **Trade sizes on Polymarket.** In our 832,257 trades ($51.3 million), the median trade is $6.48,
     92% of trades are under $100, and trades of $1,000 or more are about 1% of trades but 45% of the
     money. This describes trade sizes only. Trade size does not identify the trader: bots split large
     orders, and one trader can place many small bets. A claim about retail versus large traders needs
     wallet addresses, which our trade pull does not store.
104. **Thin versus busy markets:** split company-days into thirds by Polymarket dollar volume in the 24
     hours and report the Sharpe ratio in each third. If pure news predicts best in the thinnest
     third, news is absorbed slowly where little money trades.
105. **Who trades on the news:** for each company-day, the net money flowing to the good-news side over
     the 24 hours (buys of it minus sells), split into trades under $1,000 and trades of $1,000 or
     more. Regress each on the pure-news weight w(k,D): which group trades in the direction pure news
     points?
106. **Capacity:** the average money traded in the contracts the strategy holds, which bounds how much
     it could place without moving prices.

## 12. Result

107. **The claim holds if,** in the test period: the pure-news portfolio's Sharpe ratio beats raw
     news; predictable news earns little, meaning the t-statistic of the predictable-news portfolio's
     average daily money return (step 77), t = mean / (standard deviation / √days), is below 1.96 in
     absolute value; and the Polymarket Sharpe exceeds the stock Sharpe on the
     same news. Together these say Polymarket prices company news less efficiently than the stock
     market, and steps 104 and 105 say where and by whom.
108. **Outputs:** `data/news/news_shocks.parquet`, the daily portfolio returns for every predictor and
     market, the tables from steps 93 to 106, and a short write-up for Link.

---

## Still open

| Item | Needed from |
|---|---|
| Label the 200-article hand check (step 30) once the full matching run finishes | You |
| Drop the unused 2022-2024 URLs (89,114) and the 571,000 Instagram/Facebook-only URLs | You |
| Push the commits so Link can pull them | You |
| Update the pipeline slide: matching is one question per article to Qwen3.5-4B, the split is by day, and MSRR is the main model | You, if wanted |
