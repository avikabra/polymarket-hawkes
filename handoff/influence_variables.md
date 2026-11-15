# Influence variables: what decides whether an article matters to a contract group

Today's match score has two terms: the logit of the cosine between the article and the
company's Wikipedia page, and the contract's trading volume. This note collects research-backed
variables that can extend it, a label-free way to combine them, and an A/B ladder to test them.
Four literatures went into it: finance and news analytics, healthcare record linkage, legal
e-discovery, and information retrieval.

Two rules apply to every variable.

- A variable uses only information available at the article's time. GDELT dates articles to
  the day, so "before the article" means data from earlier days. The later price-reaction test
  measures moves after the article, and a variable built from post-article data would make that
  test circular.
- The weights come from unlabelled data. The roughly 900 hand labels verify the result and
  never set it.

Citations below were checked against publisher, arXiv, NBER or RePEc records on 2026-11-03.
"Partly verified" means the metadata checks out but the specific claim came from an abstract or
a secondary summary.

## 1. Candidate variables

### 1.1 Subject salience: is the company the story's subject?

- Source: RavenPack's relevance score (REL, 0 to 100) rates how central a firm is to a story.
  Academic users filter at REL ≥ 75. RavenPack's own documentation was not reachable, so the
  definition comes from academic papers, for example arXiv 2307.02673 (partly verified). The
  WRDS RavenPack guide is the primary source to read. Dunietz and Gillick (EACL 2014, "A New
  Entity Salience Task with Millions of Training Examples") label salience automatically from
  NYT abstracts and report a 34% gain over a strong baseline (partly verified; their feature
  ranking is unconfirmed).
- Computation, per article-company pair:
  - mention count
  - mention in the headline (0/1)
  - mention in the lede (0/1)
  - first-mention character offset divided by document length
  - the company's share of all organization mentions
  - the number of distinct companies named, as a list-article penalty

  The inputs are GDELT's organization offsets and the fetched headline and lede.
- Timing: article-only, so it is safe.
- Cost: negligible.

### 1.2 Novelty: is the information new?

- Source: Tetlock, "All the News That's Fit to Reprint," Review of Financial Studies 24(5),
  2011 (verified). He measures staleness as the textual similarity of a story to the firm's
  previous 10 stories. Prices react less to stale news, and the same-day return on stale news
  predicts a reversal over the following week. Fedyk and Hodson (Journal of Financial Economics
  149(1), 2023) find in their working-paper version that news recombining old information moves
  prices and then reverses (partly verified). The published article centres on an experiment.
- Computation:
  - novelty = 1 − max cosine between the article and the company's previous 10 articles
  - a second version against all of the company's articles from the prior 2 days

  The inputs are the same embeddings the matching uses, and the earlier articles must come from
  earlier days.
- Timing: safe when the comparison set comes from earlier days.
- Cost: low. It needs one similarity search per article within the company's stream.

### 1.3 Abnormal news volume: is something happening to the company?

- Source: Kleinberg's burst model ("Bursty and Hierarchical Structure in Streams," Data Mining
  and Knowledge Discovery 7, 2003). The two-state automaton is the special case most
  implementations use (partly verified). On attention more broadly: Da, Engelberg and Gao, "In
  Search of Attention," Journal of Finance 66(5), 2011 (partly verified). In their data,
  abnormal search volume predicts higher prices within about two weeks and a reversal within
  the year.
- Computation: a z-score of the company's daily article count against its trailing 60 days, or
  the burst state from the two-state model. Both use counts through the previous day.
- Timing: same-day counts include articles published later that day, so the build uses counts
  through the previous day.
- Cost: negligible.

### 1.4 Event type matching the contract type

- Source: Boudoukh, Feldman, Kogan and Richardson, "Information, Trading, and Volatility:
  Evidence from Firm-Specific News," Review of Financial Studies 32(3), 2019 (verified). News
  they can identify by event type explains 49.6% of overnight volatility, against 12.4%
  intraday. Their taxonomy has 14 categories and 56 subcategories, described in the NBER
  working-paper predecessor w18725.
- Computation: classify each article into an event type (earnings, KPI or operating metric,
  valuation or financing, M&A, product, legal or regulatory, executive) from GDELT themes plus
  a headline classifier. Set a flag when the type matches the contract group's type.
- Timing: article-only, so it is safe.
- Cost: a keyword and theme mapping costs nothing. A zero-shot classifier costs a small
  Bouchet run.

### 1.5 Contract-specific relevance: does the article speak to this contract's question?

- Source: query-focused passage ranking from information retrieval. Applying it to contract
  questions is our own construction, and no paper tests it in this setting.
- Computation:
  - the cosine between the article and a query built from the contract question, for example
    "Microsoft Q3 Azure revenue growth above 38%"
  - for numeric contracts, the distance between amounts in the text and the strike:
    log(|amount − strike| / strike)
  - a count of forward-looking words (expects, guidance, outlook, forecast)
- Timing: article and contract metadata only, so it is safe.
- Cost: one extra embedding per contract group.

### 1.6 Source prominence

- Source: Fedyk, "Front-Page News: The Effect of News Positioning on Financial Markets,"
  Journal of Finance 79(1), 2024 (verified). Front-page articles see 240% more trading volume
  and a 176% larger absolute excess return in the first 10 minutes. These figures come from
  the published version. Earlier drafts report different numbers.
- Computation:
  - a wire-service flag (Reuters, AP, Bloomberg, Dow Jones)
  - an originator flag: the first domain to carry a story cluster, by earlier days only
  - the domain's trailing share of the company's coverage

  GDELT carries no page-position field, so these are proxies for prominence.
- Timing: safe with the earlier-days rule.
- Cost: a short hand-made domain list.

### 1.7 Contract state at the article's time

- Source: none. This is our own derivation from option logic: news matters more for a contract
  that is still uncertain and close to expiry. The thesis should present it that way.
- Computation:
  - the absolute log-odds at the close of the previous day
  - days to expiry
  - for price contracts, moneyness = (previous close − strike) / (volatility × √time)
- Timing: previous-day values only.
- Cost: negligible.

### 1.8 Pre-article contract volume

- This is today's volume term with the window moved. The current code uses the 24 hours after
  the article (`src/matching/liquidity_signal.py:108`), which is circular. The new term
  compares volume over the 14 days before the article against a longer earlier baseline.

### 1.9 Lower priority

- Tone deviation: GDELT tone against the company's trailing norm. Text-sentiment return
  prediction has support in Ke, Kelly and Xiu, "Predicting Returns with Text Data" (NBER
  w26186, verified as a working paper). GDELT's tone field is noisy.
- LLM materiality rating: Lopez-Lira and Tang (arXiv 2304.07619, partly verified) find that
  GPT-4 headline scores anticipate the initial market response and forecast later drift. The
  current abstract makes no next-day-return claim. Risks: cost at scale, and the model may
  remember outcomes for events before its training cutoff.

### 1.10 Hedge-fund triggers

Public practitioner documents from funds were not found. The closest evidence is RavenPack,
the news-analytics vendor quant funds buy. Academic users of its data commonly require REL ≥ 75
and an Event Novelty Score of 100, meaning the first story on an event within 24 hours.
Variables 1.1 and 1.2 rebuild those two filters from our own data.

Other common triggers fall outside our data: earnings surprise against analyst consensus,
options activity, analyst revisions, and social-media velocity. Intraday timing is also out of
reach, because GDELT gives only the day.

## 2. Combining the variables without labels

### 2.1 Fellegi-Sunter record linkage, fitted by EM (test first)

- Source: Fellegi and Sunter, "A Theory for Record Linkage," JASA 64(328), 1969 (verified).
  Enamorado, Fifield and Imai, APSR 113(2), 2019 (fastLink, verified as a scalable
  implementation). The EM-without-labels and error-rate details come from summaries and need a
  read of the paper.
- Method:
  - Each article-company pair gets a vector of levels, one per variable family, for example
    salience high, medium or low.
  - EM treats "match" as a hidden class and estimates two probabilities for every level:
    m = P(level | match) and u = P(level | non-match).
  - A pair's weight is the sum of log(m/u), which turns into a posterior match probability.
- Why it fits: it is the only method in the four literatures that sets both the weights and the
  cutoff from unlabelled data. It also reports an estimated false-discovery rate, the average
  of 1 − posterior over the pairs kept, which the labelled sample can check directly.
- Risk: the method assumes the variables are independent given the class. Salience,
  name count and headline presence move together, so they go in as one combined salience
  family. Without that, the posteriors come out overconfident.

### 2.2 Alternative: weak supervision

- Source: Ratner et al., "Snorkel," PVLDB 11(3), 2017 (partly verified).
- Method: each variable votes +1, −1 or abstain, and a generative label model learns how
  accurate each voter is without labels. It is another label-free combiner, run as the second
  arm of the A/B test.

### 2.3 Control

The current plan's two-component mixture on a single summed score stays as the control arm.

## 3. Setting and defending the cutoff

- Label-free placement uses one of two rules:
  - The Fellegi-Sunter posterior at a stated false-discovery rate q.
  - The knee in the curve of cumulative pairs against score rank. Cormack and Grossman, SIGIR
    2016 (verified), describe the knee rule as a geometric stopping rule, so it is a published
    rule with no probabilistic guarantee.
- Certification: draw a random sample from below the cutoff and label it (an elusion sample),
  then report missed matches with a Clopper-Pearson interval. The probabilistic guarantee comes
  from two published sample-based methods:
  - Cormack and Grossman's target method: 95% reliability at a 70% minimum recall.
  - Callaghan and Müller-Hansen (Systematic Reviews 9:273, 2020, verified): a hypergeometric
    test against a recall target.
- Requirement: certification needs a random sample. The stratified labelled sample in the
  plan verifies precision. A separate random draw of about 200 pairs below the cutoff
  certifies recall.

## 4. A/B ladder

Each step adds one family to the previous step. Each step runs through the Fellegi-Sunter
combiner, with Snorkel and the summed-score mixture as comparison arms.

| Step | Score contains |
|---|---|
| 0 | logit(cosine) only |
| 1 | + subject salience (1.1) |
| 2 | + novelty (1.2) |
| 3 | + abnormal news volume (1.3) |
| 4 | + event type matching the contract type (1.4) |
| 5 | + contract-specific relevance (1.5) |
| 6 | + source prominence (1.6) |
| 7 | + contract state and pre-article volume (1.7, 1.8) |

Each step reports:

- how cleanly the scores split (estimated false-discovery rate at q = 0.10, and knee
  sharpness)
- precision and recall on the labelled sample
- recall certified on the random elusion sample

The step after which nothing improves fixes the variable set. The price-reaction test (do
matched articles move prices more) comes later, under a separate plan. It is the final check
on whichever step wins.

## 5. Where this sits in the thesis

The closest published work linking news to Polymarket is Ibrahim and Zaki, "Price
Dislocations, News Citations, and Epistemic Leverage on Polymarket" (arXiv 2609.06005,
September 2026, verified). They find articles that quote odds and attribute each quote to a
market with an LLM. No published method scores how much an article influences a contract group
from label-free linkage weights. The search behind that claim covered the four literatures
above at abstract depth, so the novelty claim needs a full literature review before it goes in
the thesis.

These variables plug into section 6 of `handoff/pull_plan.md`. They replace its match-score
terms and its two-group weight fit.
