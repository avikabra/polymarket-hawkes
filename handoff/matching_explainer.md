# Article-to-company matching: explainer for Link

Status: the user approved this design on 2026-11-05. It replaces the earlier per-pair design (see "What this replaced and why"). Nothing has been run. Model speed, the number of articles, the token limit and the pass bar are unmeasured or unset. Every number below that is not marked as measured is either a fixed fact from the code or an illustration.

Function names, not line numbers, cite `src/ingest/` and `scripts/ingest/`, because those files are still changing.

## 1. What this step does

GDELT gives us articles that contain a company's name. Many of them only mention the company in passing ("shares of Apple fell with the rest of the market"). Matching decides which of our 61 companies each article is primarily about. The articles and companies that pass go to the news shock stage, which embeds the matched articles and subtracts what the prior state predicts.

Kelly's paper (Didisheim, Kelly, Pourmohammadi and Tian, "The Inefficient Pricing of News", NBER w35093) has no matching step. Its articles arrive with Reuters vendor tags that already assign each article to one stock. We have no vendor tags, so we build a substitute in two stages.

Stage one is broad name extraction: GDELT name search, article fetch, name recheck and duplicate URL removal. It builds the article base and favors recall. Stage two narrows the base with a local language model, Qwen3.5-4B. The model reads each article once and returns the list of our companies the article is primarily about, which can be empty.

The design adds no math to the thesis. The user decided that the thesis's novel math comes from a later part, not from matching.

## 2. The rule that governs the dates

GDELT dates an article to the day only (`timestamp_precision = "day"`, set in `write_month` in `src/ingest/gdelt_pull.py`). The hour of publication is unknown. Anything downstream that needs a time must treat the whole day D as unusable for the reaction window, as the rest of the pipeline already does. Matching uses no prices and no volume, so it does not touch this rule.

## 3. Inputs

| Input | Source | File | Notes |
|---|---|---|---|
| Kept articles | Fetch shards, one row per fetched URL | `data/news/fetched/part-*.parquet` | Articles that passed the name recheck keep their text. Failed and no-name articles keep only `url` and status. The model input is built from `headline`, `lede` and `body`, so the model does not read the source and date line. There is no `pairs.parquet` |
| Company ids and names | Seed list | `config/companies.yaml` | All 61 go into the shared system prompt |
| Token limit for article text | Set from the distribution of measured article lengths | not yet set | Open question 1 |
| Model | Qwen3.5-4B, open weights, Apache 2.0 | Hugging Face id to be confirmed on the cluster | Not downloaded |

How the articles were found, in order:

1. GDELT GKG 2.1 files come from the public file list (`masterfilelist.txt`, one zip per 15 minutes). They are read in memory, filtered and discarded (`pull_month` in `src/ingest/gdelt_pull.py`).
2. A record becomes a candidate for a company when a company name appears as a whole word with exact capitalization in the record's `V2Organizations` or `AllNames` field (`whole_word_pattern`). Each row records which field matched. Tickers are never used.
3. Days scanned: for the contract period (2025-01-01 to 2026-10-31), the Eastern-time days on which the company has an open kept contract (`contract_ranges` in `src/ingest/article_days.py`). For 2022 to 2024, only days 1, 8, 15 and 22 of each month (`training_days` in `config/ingest.yaml`), with a sample of at most 50 URLs per company per month, ranked by a hash of the record id so a rerun draws the same sample.
4. Each candidate URL is fetched once (`run` in `src/ingest/body_fetch.py`). The fetch runs as 4 parallel Slurm tasks. Each task takes the URLs whose hash falls in its part and opens 1 connection per domain. The text is extracted with trafilatura.
5. Right after each chunk, the name is searched again in the extracted text (`names_found`). An article without the name is dropped. Failed and no-name articles keep only `url` and status, so their text is discarded as the fetch goes. Drop reasons in the log are `not_fetched`, `fetch_failed:<type or status>`, `empty_body`, `name_missing`.
6. One article is kept per URL. Same-headline same-day duplicates are removed later, after the mapping, on matched articles only (flow step 10).

Measured on the GDELT pull: 5,084,070 rows in all. In the contract period, 4,986,773 rows and 4,284,645 URLs. Instagram makes up 21.6% of the rows and Facebook 16.8%, likely from page boilerplate that names the company.

The docstring of `body_fetch.py` records a 77.8 percent fetch success rate and 11.4 articles per second, measured on an earlier sample. Neither number is a result of the new pull.

## 4. Step-by-step flow

1. Read the kept articles directly from the fetch shards.
2. Build one shared system prompt, word for word: "You label news articles. Return every company below that the article is primarily about. A subsidiary, product or brand counts as its parent company. A company mentioned only in passing does not count. If none apply, return an empty list." The 61 company ids and names follow it. The prompt text gets a version label that is saved with the result.
3. Build the per-article input: `Headline:` and `Text:` only. The text is the headline, lede and body, with no Source or Date line, cut at one token limit that we set from measured article lengths. An article that the limit cuts gets a cut flag.
4. Constrain the output with a JSON schema whose items are an enumeration of our company ids, with no repeats. Valid outputs are `{"companies": ["amazon"]}`, `{"companies": ["amazon", "walmart"]}` and `{"companies": []}`. The model returns no probabilities, and the answer needs no cutoff.
5. Run vLLM 0.17 or later in offline batch mode as one Slurm job on one L40S. Settings: thinking off, temperature 0, a short output limit, prefix caching on. The shared system prompt is the cached prefix. How prefix caching interacts with structured outputs is unconfirmed, and the test run checks it. The model needs a new Python environment, `.venv-llm` in `thesis-ingest`, because the project's environment pins torch below 2.3 for the Intel Mac and that version very likely cannot load Qwen3.5. The sbatch pattern is in `scripts/bouchet/ingest_07_embed.sbatch`. Per the project rules, the user approves the Bouchet login and the main session runs the cluster commands.
6. Write results in chunks to disk, so a killed job resumes at the first missing chunk.
7. Log after each chunk: articles done and remaining, articles per second, estimated time left, tokens in and out, GPU memory, the share of articles with no company, one company and several companies, the cut count and the failed count. Articles that fail go to a separate file for a rerun.
8. Run `--limit 1000` first. It measures speed, run time and tokens, and it shows sample answers to read. It also checks whether prefix caching works together with structured outputs.
9. Check against hand labels (section 6).
10. Map shard by shard. Once a shard is fully mapped, remove the text of its articles that returned no company. After mapping, remove same-headline same-day duplicates among matched articles, keeping the longest body, and write `data/news/matches.parquet` with `article_id`, company list, cut flag, model and prompt version.

Only matched articles are embedded, for the news shock in section 6 of `pull_plan.md`; no embedding is kept for the rest. Matching no longer uses the Wikipedia pull (`scripts/ingest/06_pull_wikipedia.py`) or company-page embeddings.

## 5. The output constraint

The model answers with a list of company ids. A JSON schema restricts the ids to our 61 and forbids repeats, so the output always parses and never names a company outside the list. An article is matched to every company in its list. An article with an empty list has no match.

No score, cutoff or fitted parameter exists. The model is used as is. The only thing we tune is the prompt, and only through the check in section 6.

The constraint guarantees the format. It does not guarantee the content. See failure mode 1.

## 6. Validation

The user sets the pass bar before seeing any results. The bar is 98 percent for both precision and recall (open question 2 asks how to justify it).

Then the check runs in this order. Pass bar: 98 percent for both shares.

1. Draw 200 random articles from the run, spread across companies, including some that returned no company.
2. The user marks which of the 61 companies each article is primarily about, without seeing the model's answer.
3. Compare. Precision is the share of the model's companies that the user marked as right. Recall is the share of the user's true companies that the model found.
4. If the model misses the bar, change the prompt, rerun from the `--limit 1000` test, and check a fresh 200 articles. The labeled 200 are not reused after a prompt change, because the prompt was tuned on them.

Error bars, from the normal approximation for a proportion at 95 percent confidence. Precision rests on the number of companies the model returned, and recall on the number of true companies. Each is likely near 100 to 250 items in the 200 articles, which is unknown until the labels exist.

| Items behind the rate | Margin at 50% | Margin at 80% | Margin at 90% |
|---|---|---|---|
| 200 | about 7 points | about 5.5 points | about 4 points |
| 100 | about 10 points | about 8 points | about 6 points |

Two limits follow. First, a pass bar of 90 percent cannot separate a model at 85 percent from one at 95 percent with these samples. Second, the sample deliberately includes articles with no company, so its mix differs from the real mix. Report the none-share of the sample next to the none-share of the full run, and reweight if they differ. Margins also widen for any per-company statement, since 200 articles over 61 companies leave only a few per company.

## 7. Worked example (illustrative, not a result)

Three invented articles. The company ids are examples.

| Article | What the model reads | Output | Reading |
|---|---|---|---|
| 1 | Headline "Apple unveils new iPhone as supply costs ease"; the text discusses the launch and Apple's margins | `{"companies": ["apple"]}` | One company |
| 2 | Headline "Stocks fall as inflation data surprises"; one sentence says "tech names such as Apple and Nvidia led the drop" | `{"companies": []}` | None. Both companies are passing mentions |
| 3 | Headline "Amazon nears deal to buy grocery chain from Walmart"; the text covers the deal terms for both | `{"companies": ["amazon", "walmart"]}` | Several companies |

In article 1, the stage-one search found "Apple" and the model keeps it. Had the article said only "the iPhone maker", stage one would not have found it, but the model might still return `apple` (failure mode 4).

## 8. Failure modes

None of these has been measured. Each entry says what we would see if it happened.

1. Forced JSON can be valid and still wrong. The schema guarantees the format and the company ids, not the judgment. A well-formed `{"companies": ["apple"]}` for an article that only mentions Apple parses without error. We would see a clean run with a 0 failed count and low precision in the labels. The failed count measures format and run failures only, so it says nothing about accuracy. The RANLP 2025 paper on structured output (see Sources) bears on this question.
2. Picking several labels is harder than one. A yes/no on one company is an easier task than choosing a subset from 61 names. A 4B model may return too few companies (stopping at the first) or too many (listing every name it recognizes). We would see recall fall on articles with several true companies and precision fall on market wraps. Report both by the number of true companies per article (0, 1, 2 or more).
3. The model may return a company the name search did not find for that article. The model reads the text and the 61 names, and not the stage-one list. A subsidiary, product or brand mention ("the iPhone maker", "AWS") can produce a correct company that stage one missed, and a wrong guess looks the same. We decide nothing about this now. We would observe a returned id that is not among the company names found in that article's text. Count these, report their share of all returned companies, and read a sample before deciding what to do with them.
4. "Primarily about" is a fuzzy line. An article on a chip supplier that spends three paragraphs on Apple's orders, or a market wrap with a paragraph on Apple, sits between "primarily about" and "passing mention". Two reasonable people disagree, and so will the model. We would see label disagreement concentrated in such articles. Agree on written rules for borderline cases before the user labels (open question 4).
5. The 200-article check has wide error bars. Section 6 gives the numbers. A pass at 88 percent on 200 articles is compatible with a true rate near 82 percent, and a company-level claim rests on a handful of articles.
6. Truncation drops the relevant passage. The text is cut at the token limit, so a long article whose company section comes late reads as a passing mention or as off-topic. We would see recall fall with article length, and empty lists among long articles. Check the none-share by length bin and by cut flag. The limit is set from measured lengths for this reason.
7. Recall loss upstream. The model only sees articles that stage one found. An article about a company that never uses its exact capitalized name in `V2Organizations` or `AllNames`, or uses a name missing from `config/companies.yaml`, never enters. The all-caps headline case ("APPLE UNVEILS") and the casing of `AllNames`, which the docstring calls unverified, make this worse. No amount of model quality repairs it, and the 200 labels cannot detect it, because they are drawn from articles that already exist. A separate check is a small hand-checked sample of articles from the raw GKG day that mention the company by another route.
8. Generic names reach the model. "Windows", "Mac", "Gemini", "Converse" and similar names, and person names in `AllNames` (Harrison Ford, Michael Dell), pass the name search and the name recheck. The model is the first real filter for them, and also where a small model errs: an article about the Gemini zodiac sign or Converse sneakers might be read as about a company. We would see matches concentrated in a few companies, and low precision for those companies. Report precision by company for the generic-name set.
9. Failed and paywalled fetches. Articles whose fetch fails never reach the model. Older URLs (2022) die more often, and paywalled domains return little text. Survivors are a non-random subset: more recent, from more open publishers. We would see fetch success fall by year and the surviving sources skew toward a few domains. The per-chunk fetch log records each fate, so this can be checked. A paywalled page that returns only a teaser will often get an empty list because the evidence is missing.
10. Day precision and time zone. GKG `DATE` is the record date in UTC and takes its day from the first 8 characters. Contract days are Eastern time. An article published at 9 pm ET on the 4th carries day 5. The date also reflects crawl time, so an evergreen or syndicated page can carry a later day than its real publication. Matching does not use the date, but every later step that links an article to a contract day inherits the error. It dilutes the reaction signal and does not leak the future.
11. Training data overlap. Qwen3.5-4B was trained on web text that probably includes some of 2022 to 2024, and perhaps some of these articles. The task is reading comprehension on a text the model is given, which limits how much memory of the event can help, but the thesis should disclose the overlap. The model cannot have seen contract-period articles from late 2026 if its cutoff is earlier, so accuracy could differ between the two periods. Compare precision and recall by period.
12. Small-model errors on non-English text and long pages. A 4B model reads English well and other languages less well. GDELT includes non-English sources. We would see lower agreement with the labels and more empty lists on non-English articles. Report results by language if the labeled set contains enough, and consider dropping or flagging non-English articles before the run. Long pages with navigation text, comments and related-links blocks (body extraction is imperfect) also confuse a small model.
13. Prompt sensitivity. Small changes in wording ("primarily about" against "mainly about", the order of the company list) can change the output for borderline articles. We would see different match sets from two reasonable prompts. The prompt version is saved for this reason, and a changed prompt restarts the test and uses a fresh 200 (section 6).
14. Duplicates that survive. Dedup runs after mapping on matched articles only, by same headline and day. A wire story reprinted under different headlines is not removed, so it receives several matches. We would see clusters of near-identical bodies on one day.

## 9. What this replaced and why

Per-pair yes/no with a probability P. The design before this one sent each (article, company) pair to the model as its own prompt and asked "Is this article about [company], or does it only mention it in passing? Answer yes or no." It read the next-token probabilities of "yes" and "no", computed P = p(yes) / (p(yes) + p(no)), and matched pairs with P >= 0.5. The user dropped it for two reasons. One pass per article is cheaper than one pass per pair, since an article that names three companies cost three passes. And a direct answer needs no cutoff, since P was an uncalibrated score and 0.5 was only the point where the model's preference flipped.

Fellegi-Sunter. The older plan used a Fellegi-Sunter mixture model fitted by EM, with match weights taken from the fit. It was dropped. The user replaced it with a fixed score and then with the LLM.

The cosine plus volume score. The second design computed score = logit(cos) + z, where cos is the cosine between an article embedding and the company's Wikipedia page, z is a volume z-score, and a pair matched when the score was at least 0. A cosine is not a probability, so taking its logit and calling 0 the cutoff meant nothing. The earlier rho of 0.51 between the score and the Polymarket reaction (against 0.25 for the embedding alone) was tautological: the volume term and the target were computed over the same window, so a high-volume day with a large move scored high on both. These numbers came from BGE-era runs and the user reported them.

Versions A, B and C. Version A used the cosine alone, B added Polymarket volume and C added stock volume. They are dropped with the score.

Choosing by price moves. The plan was to keep the version whose matched articles moved prices most. That is circular, because it assumes that real matches move prices, which is the thing the thesis tests. A version that keeps articles on days with large moves would win by construction.

The regression. Part of the earlier plan fitted a regression for the match weights. It is not needed, because the matcher has no fitted parameters.

## 10. Verified, decided, unmeasured

| Item | Status |
|---|---|
| GKG 2.1 public files, `V2Organizations` and `AllNames` whole-word match with exact case, day precision | Verified in `src/ingest/gdelt_pull.py` |
| Fetch in 4 hash-split tasks, per-chunk name recheck, drop reasons, shard layout | Verified in `src/ingest/body_fetch.py` and `scripts/ingest/05_fetch_articles.py` |
| Text removal for no-company articles per mapped shard, post-mapping dedup | Verified in `scripts/ingest/08_map_companies.py` (`strip_empty`, `--build`) |
| GDELT counts (5,084,070 rows; contract period 4,986,773 rows, 4,284,645 URLs; Instagram 21.6%, Facebook 16.8%) | Measured |
| Training days 1, 8, 15, 22 and 50 per company-month | Verified in `config/ingest.yaml` and `src/ingest/article_days.py` |
| 77.8 percent fetch success, 11.4 articles per second | Reported in the `body_fetch.py` docstring from an earlier sample |
| Rho 0.51 vs 0.25 for the old score | Reported by the user, BGE-era, not re-derived |
| One pass per article, 61-company list, shared system prompt, JSON schema output, no probabilities, no cutoff, vLLM 0.17 or later, one L40S, thinking off, temperature 0, `--limit 1000` test, 200-article blind check, output file and its columns | Decided by the user |
| Hugging Face model id, token limit, output length limit | Not set (pass bar is set at 98 percent) |
| Prefix caching together with structured outputs | Unconfirmed; the test run checks it |
| Run time, GPU memory, number of articles, share with none, one and several companies, precision, recall | Unmeasured |
| Whether the case of `AllNames` is preserved | Unverified (stated in the `gdelt_pull.py` docstring) |

## 11. Open questions

1. What token limit? Set it from the distribution of measured article lengths, once the fetch has run. Should the cut keep the start only, or the start plus the passages around the company name?
2. The pass bar is 98 percent for precision and recall. How is it justified given the margins in section 6? At that level 200 articles allow few errors.
3. What is the exact Hugging Face id, and does vLLM 0.17 or later support Qwen3.5-4B with thinking off, prefix caching and structured outputs together?
4. How are borderline cases written down so the user's labels are consistent?
5. Are non-English articles read, flagged or dropped?
6. How is recall loss upstream checked (failure mode 7)?
7. How many articles are there, and how long does the run take? If it is slow, does the plan sample articles or cut the token limit?
8. In which time zone is "midnight after D" measured, given that GDELT days are UTC and contract days are ET?
9. Resolved: a multi-company article counts for each of its companies in the shock stage.
10. What happens to a returned company that stage one did not find for that article (failure mode 3)?

## Sources

- vLLM documentation, "Structured Outputs". It describes how a JSON schema constrains the generated text.
- The RANLP 2025 paper on structured output with language models. It studies how forcing a format affects answer quality.
