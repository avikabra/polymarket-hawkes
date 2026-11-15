# Novel Math Design — Thread 1 (Liquidity-Validated Matching) & Thread 2 (Ladder Reaction Model)

## Real results, 2026-09-29 (both threads implemented, wired in, run at full scale on Bouchet)

**Thread 1 acceptance result — POSITIVE, strong.** `scripts/09b_matching_ablation.py`, full
corpus (27,132 verified pairs, 16,458 with a real achievable 24h window):
```
Spearman(embedding-only score, |y_logit_24h|): rho=0.2493  p=1.4e-231
Spearman(joint score,          |y_logit_24h|): rho=0.5124  p≈0
```
The joint (liquidity-validated) score correlates **more than double as strongly** with the
realized market reaction as embedding similarity alone — a large, highly significant gap at
real scale, not a marginal or noise-level result. This is the acceptance evidence the design
doc's Q3 required; report it as-is in the thesis (do not re-tune weights to inflate it further
without re-validating out of sample).

**Thread 2 real impact — substantial, category-differentiated, behaves exactly as designed.**
Real cohort-level isotonic correction on `tuples.parquet` (35,997 valid-24h rows):

| Category | Mean \|correction\| (log-odds) | Mean real cohort size |
|---|---|---|
| `corporate_event` | 0.000 (exact) | 1.0 (singleton, as designed) |
| `price_ladder` | 0.562 | 160.5 |
| `revenue_ladder` | 0.610 | 59.5 |
| `valuation_ladder` | 0.287 | 337.9 |

58.7% of valid rows (21,115/35,997) were materially changed by the correction. `corporate_event`
landing at exactly zero correction with cohort size exactly 1.0 confirms the singleton-passthrough
logic is working correctly on real data, not just in synthetic tests.

**Feasibility gate is unaffected by either thread** (both are purely additive columns) — still
`corporate_event` PASS, other four FAIL for the same real, honest reasons documented in
`reports/bouchet_overnight_run_status.md` §3c (now recalibrated, see the commit history).

*Adversarially critiqued 2026-09-29 (one full revision round — five real issues found and
fixed, see below). Implementation authorized by Avi 2026-09-29 without a further review
pass — "write up the plan and implement, don't wait for me." Verified data facts below are
from direct inspection of this repo's real data (universe.parquet, contract_groups.parquet,
the overnight run's tuples.parquet/shock_embeddings.parquet), not assumption.*

## Grounding facts (verified, not assumed)

- `parent_event_id` is hardcoded `None` at the source (`src/polymarket/gamma.py:248`) —
  never populated, not a "sometimes missing" field. Do not use it for ladder grouping.
- `contract_groups.parquet`'s `group_id` (company × metric × expiry-**month**) is coarser
  than a true no-arbitrage ladder: 103/158 ladder groups (65%) span multiple `end_at`
  values, and 66/158 (42%) mix `strike_direction` within one `group_id`. **Monotonicity
  only holds within a `(group_id, end_at, strike_direction)` cohort.**
- Real ladders are large where it matters: Apple/Microsoft/Amazon/Google Nov-2025 price
  ladders have 53–59 member strikes each.
- `valid_1h = valid_6h = 0%` corpus-wide (confirmed, overnight run) — only `y_logit_24h`
  has meaningful coverage, because this corpus is ~99.98% GDELT (day-precision).
  **`y_logit_24h` is the only real target; 1h/6h are kept for completeness/future corpora
  only and must not be reported as findings.**
- Per-category expectations (Thread 2): `price_ladder` is the primary beneficiary (large
  real ladders); `valuation_ladder`/`revenue_ladder` real but modest; `corporate_event` is
  a singleton category by construction (no ladder — expected, not a gap);
  `market_cap_ladder` has only 4 markets total — too few for cohort pooling to help.

## Thread 1 — liquidity-validated embedding-space matching

**Formula (Q1, Option B):** `match_quality_logit = w1·logit(clip(cosine, ε, 1-ε)) + w2·z(liquidity_signal)`,
`match_strength = sigmoid(match_quality_logit)`. A log-odds combination of standardized
text-similarity and liquidity signals — explainable in one sentence, reuses the repo's own
log-odds convention. Start `w1=w2=1.0` (fixed); tuning against labels is a stretch goal, not
required. **Caveat to state in the thesis text**: this borrows the log-odds combination
*form*, not a literal probability model — `logit(cosine)` is a metaphor reuse, not a real
probability.

**Liquidity signal (Q2):** abnormal volume relative to each market's own trailing baseline
(14-day median/std, backward-looking only — no leakage), aggregated across a group's member
markets (sum volume, max |price-impact| via `reaction_windows.compute_reaction_windows`,
reused not reimplemented). Respects day-precision: GDELT rows only ever get a ≥24h window.

**Validation (Q3) — REQUIRED, not optional:** `scripts/09b_matching_ablation.py` must show
the joint score correlates with realized `|y_logit_24h|` better than embedding-only cosine,
out of sample. This is the one artifact that distinguishes "novel method" from "feature
engineering" — Thread 1 is not done without it.

**Stated limitation:** a liquidity spike near an article's timestamp is evidence *something*
moved the market then — not proof this specific article caused it (a different concurrent
article about the same company could be the true cause). Validates "a genuine event
occurred," not "this exact article was it." Disclose in the thesis text.

**Lands in:** script 09 as a new `--joint` path (mirrors existing `--llm`/`--openweight`
pattern), alongside (not replacing) the rule-based verifier. Script 08 (retrieval) untouched.

## Thread 2 — monotone parent/child strike-ladder joint reaction model

**Formula (Q1, Option C):** weighted isotonic (PAVA) projection of each event's independently-
computed `y_logit_24h` values across its `(group_id, end_at, strike_direction)` cohort,
weighted by `volume_24h_usdc`, `increasing=(strike_direction=="below")`.

**Why this is genuinely joint, not post-hoc smoothing (state explicitly in the thesis):**
weighted isotonic regression under squared loss is the MLE-consistent projection onto the
monotone cone — each corrected value is a function of *every other market's* observed
reaction in the cohort (via PAVA's pooling), not of its own value alone. Two markets with
identical raw reactions can get different corrected values depending on their neighbors.
The two-step computation (independent estimate → isotonic correction) is a computational
convenience (PAVA is the closed-form solution), not evidence the model is separable.

**Interaction with purging.py (Q2):** separate stage, does not touch the ridge regression.
Adds `y_logit_24h_ladder` (+ 1h/6h for completeness) as new columns in `tuples.parquet`;
script 13 just carries them through like it already does for `y_logit_6h` today. Enables a
clean ablation: train script 16 once on `y_logit_24h`, once on `y_logit_24h_ladder`, same
features/splits.

**Out-of-sample discipline (Q4):** verified safe — the isotonic projection is per-event,
cross-sectional, backward-looking-only in its weights, and all rows in one cohort share the
same `market_resolved_at`-derived split (since cohort members share `end_at` by
construction), so there's no train/val/test leakage. State this reasoning in the methods
section explicitly — don't leave it for a grader to assume.

## File-level implementation (dependency order)

**Thread 1:** `src/utils/bars_io.py` (extract shared loader from script 12) →
`src/matching/liquidity_signal.py` → `src/matching/joint_verifier.py` →
`scripts/09_llm_verify_matches.py --joint` → `scripts/09b_matching_ablation.py` (required).

**Thread 2:** `scripts/12_assemble_dataset.py` (add `end_at`/`strike_price`/`strike_direction`
columns) → cohort-size diagnostic (no code) → `src/analysis/ladder_reaction.py` →
wire into script 12 → `scripts/13_purge_and_compute_shocks.py` (carry `_ladder` columns) →
`scripts/16_train_linear_baseline.py --target` flag.

Each new module ships with tests per the original plan's verify checks (monotonicity
regression tests, synthetic-spike detection, singleton-cohort no-op, explicit no-arbitrage
direction test). Full critique history and all five fixes are in this session's transcript;
this doc is the durable summary.

## Thread 1 addendum, 2026-10-05: entity-grounding term (GDELT audit follow-up)

A GDELT GKG field audit (real local 1.4GB corpus) found that `entities`
(V2Persons+V2Organizations, already fetched for every article, used only by script 10's
dedup) was never used by the matching verifier itself. Added a third additive log-odds
term: `match_quality_logit += w3 * entity_match` where `entity_match` = does the
candidate group's company name/alias appear in the article's extracted entities
(`src/polymarket/company_filter.entity_grounding_match`, `w3=1.0` default, same
start-fixed convention as w1/w2). Wired into `score_pair_joint` (both script 09's
`--joint` path and 09b), with `entities`/`company_aliases` optional and defaulting to
`entity_match=False` — existing callers that don't pass them are unaffected.

**Validated on real local data (not synthetic)**: sampled 2025-06's real GKG file
(14,718 tagged rows) — `entity_grounding_match` against the article's own
GDELT-assigned `matched_company` aliases agrees 100% of the time (expected: both derive
from the same underlying V2Persons/V2Organizations text). The discriminating test is the
negative case: checked 500 real articles against a *different*, randomly-chosen
company's aliases (simulating a false embedding-retrieval candidate pair) — false-positive
rate 0.60% (3/500). This is a real-data precision check, not a predictive-value one.

**Not yet done** (needs Bouchet): re-run `scripts/09b_matching_ablation.py` (now wired
for entities) against the real 27,132-pair corpus to see whether this lifts Spearman ρ
above the existing 0.5124 — that's the actual acceptance test, same as the original two
terms. `scripts/bouchet/run_09b_ablation.sbatch` needs no changes to pick this up (both
script 09 and 09b load entities fresh from `build_matching_text_corpus`, not a cache).

## Thread 1 addendum, 2026-10-10: entity-grounding term REJECTED — real negative result

Ran the acceptance test. First pass (job 28424401, same day) looked like a regression
(ρ dropped from the original 0.5124 to 0.4510) but across two *different* matches.db
states (other uncommitted Bouchet work — dedup fixes, body-text refetch — changed
n_used and even the embedding-only baseline between the original run and this one), so
that comparison was confounded and not trustworthy as-is.

Fixed by making `scripts/09b_matching_ablation.py` compute **both** `joint_score`
(with entity term) and `joint_score_no_entity` (without) in the same loop over the same
loaded `member_bars`, same matches.db state, same process (job 28427474, 2026-10-10,
27,132 pairs, 14,717 with a real 24h window):

```
Spearman(embedding-only score,        |y_logit_24h|): rho=0.2331  p=9.18e-181
Spearman(joint score, no entity term, |y_logit_24h|): rho=0.5086  p=0
Spearman(joint score, with entity term, |y_logit_24h|): rho=0.4510  p=0
```

**Confirmed, confound-free: the entity term hurts.** ρ drops from 0.5086 to 0.4510 when
added, on identical data. This is a real negative result, not a bug — the entity feature
itself is accurate in isolation (see the addendum above: 100% true-positive, 0.6%
false-positive against GDELT's own company tag). The likely mechanism: `entity_match` is
a flat `+1.0` log-odds boost, the same scale as the other two terms, but it's a near-
constant for the ~90%+ of pairs where the matched company's name is genuinely present
(which is most true candidates, by construction of how this corpus was pulled) — so it
mostly just compresses/flattens the finer-grained, more informative continuous ranking
that embedding_score + liquidity_z were already providing, rather than adding real
ranking information.

**Decision**: reverted the production `--joint` path (`scripts/09_llm_verify_matches.py`'s
`_run_joint`) to the original two-term formula — it no longer passes entities/
company_aliases to `score_pair_joint`, so `entity_match` defaults to `False` and the
term is inert there. The code stays available in `joint_verifier.py`/`joint_scoring.py`,
and `09b_matching_ablation.py` keeps computing the three-way comparison, so this negative
result stays reproducible and reportable — report it in the thesis as an explored-and-
rejected extension (a legitimate, honest finding), not silently dropped. **Thread 1's
accepted, reported result remains the original two-term formula: ρ=0.5086 (recomputed
2026-10-10, consistent with the original 0.5124) vs embedding-only ρ=0.2331.**
