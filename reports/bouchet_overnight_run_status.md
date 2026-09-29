# Bouchet Overnight Run — Full Status (2026-09-28 night → 2026-09-29 morning)

*What ran, what broke, what got fixed, and what's left for a human decision. Read this first
if picking this up cold.*

## TL;DR

The full pipeline (scripts 07 → 14) ran end-to-end on Bouchet for the first time. Script 07
(matching embeddings) completed cleanly. Getting through 08–14 required finding and fixing
**8 real bugs** — all committed to `weeks-7-9-data-review` and pushed. The mechanical pipeline
is done: every stage through 14 ran to completion. **The feasibility gate (script 14) correctly
returned FAIL** — that's it doing its job, not a crash — and two substantive data/methodology
questions came up that need your judgment, not mine. See §3.

## 1. What's actually on disk (verified, `/nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket`)

| Marker | Status |
|---|---|
| `data/news/matching_embeddings/_SUCCESS` | ✅ 546,657 articles, 628 groups |
| `data/matches/_CANDIDATES_SUCCESS` | ✅ 27,132 candidates |
| `data/matches/_VERIFIED_SUCCESS` | ✅ 27,132 verified (rule-based, no API cost) |
| `data/matches/_EVENTS_SUCCESS` | ✅ 22,124 NewsEvents (real dedup now — see bug 3) |
| `data/news/bodies/_SUCCESS` | ✅ 8,533/9,795 fetched (87.1%), verified-only |
| `data/news/analysis_embeddings/_SUCCESS` | ✅ 9,795 articles, E5-large |
| `data/analysis/tuples.parquet` | ✅ 318,184 rows |
| `data/analysis/shock_embeddings.parquet` | ✅ 59,068 rows, 3 categories with real regressions |
| `data/analysis/_FOCAL_SUCCESS` | ❌ gate FAILED — see §3 |

Total: ~5.1GB, all under `pi_btk22` (never home — see `reports/bouchet_login_howto.md` §0).

## 2. The 8 bugs (all fixed, commits on `weeks-7-9-data-review`, newest first)

1. **`699928f`** — script 14 queried `verifications.market_id`, a column that hasn't existed
   since the group-keyed rewrite. Fixed by fanning group-level verified counts out to member
   markets via `contract_groups.parquet`.
2. **`d23b052`** — script 14 had the same Hive-partition parquet crash as bug 8 below (its own
   duplicated loader).
3. **`4c3c8d8`** — `resolved_at` is `NaT` for all 6,928 markets in `universe.parquet` even
   though `resolved_outcome` is 100% populated and `end_at` is in the past for all of them —
   script 01 (universe pull) never captured the actual settlement timestamp. Fell back to
   `end_at` as the best available proxy. **This is a data gap, not a methodology choice — see
   §3 for why it still needs your attention.**
4. **`d243e24`** — `NaN` (not `None`) for unresolved-market edge cases wasn't caught by a
   truthy check, crashed `compute_market_chars` on `NaT.timestamp()`.
5. **`8d371f9`** — the big one: `candidate_finder.py` computed a GDELT day-precision fallback
   date to check window overlap, but never actually stored it as `article_published_at` —
   left it `NULL` for virtually every candidate (RSS is a tiny fraction of this corpus). This
   nulled every reaction-window and price computation pipeline-wide, and made script 10's
   dedup fall back to `now()` for every event (explains bug below). Also added the missing
   `market_resolved_at` output column in script 12 that `purging.py` expected.
6. **`e3fe069`** — script 12's `_load_bars` had zero caching and was called ~298k times for
   only 6,928 unique markets (~43x redundant NFS scans) — would have taken hours; capped at
   minutes once cached.
7. **`bac3923`** — made the orchestration `sbatch` script idempotent (skip any step whose
   Makefile marker already exists) so a crash mid-pipeline doesn't require redoing completed
   (possibly slow) work — this is what let the later fixes resume cheaply instead of
   re-running body-fetch/embeddings each time.
8. **`7f25d1f`** — `pq.read_table()` on a file under `data/news/feeds`' Hive-style
   `source=<name>/year=/month=` directories collides its own plain-string `source` column
   with pyarrow's inferred dictionary-typed partition column. Fixed in scripts 11 and 14
   (their own duplicated loaders) by switching to `pd.read_parquet`, matching the pattern
   `src/news/normalizer.py` already used safely.

**A quiet confirmation from bug 5's fix:** script 10's dedup went from an exact 1:1
verified-pairs:events ratio (27,132:27,132 — no clustering ever fired, since `_should_merge`
requires both timestamps non-null) to a real 22,124 events. I'd flagged the 1:1 ratio earlier
in this session as *plausibly* benign; it wasn't — it was this same bug.

## 3. What needs YOUR decision (not something I fixed or will fix unilaterally)

### 3a. The two novel-math threads are still not implemented
Neither the liquidity-validated embedding-space matching (thread 1) nor the monotone
parent/child strike-ladder joint reaction model (thread 2) exist in code — confirmed by
direct grep before this run started (see earlier conversation). What ran tonight is the
existing *conventional* pipeline: BGE similarity + rule verifier, independent per-market
log-odds diffs, purged ridge regression. This is real, necessary infrastructure regardless
of which final formula you land on — but it is not yet the DUS-satisfying novel contribution.
I did not attempt to design or implement either thread myself; that's explicitly your call,
per the DUS mandate that you be involved in developing the new math.

### 3b. `resolved_at` data gap — real fix needed upstream, not just the `end_at` patch
The `end_at` fallback (bug 3) got the pipeline running, but it's a stopgap. Two consequences
worth your attention:
- **Train/val/test split is badly skewed**: train=2,562, val=111, **test=56,395** (95% of
  data). This is a direct effect of `end_at` values landing mostly after the hardcoded split
  cutoffs (`train_before`/`val_before` in `config/analysis.yaml`) — those cutoffs were almost
  certainly chosen assuming real resolution dates, not scheduled-expiry dates. Worth either
  re-pulling real `resolved_at` from Polymarket (script 01 fix, needs live API access) or
  adjusting the split cutoffs to match what `end_at` actually gives you.
- `parent_event_id` is 100% null in the shock embeddings output — didn't dig into this one,
  flagging it rather than guessing at a fix.

### 3c. Feasibility gate: real FAIL, not a bug
All 5 categories fail on `Min%` (0.0%, need ≥60% minute-precision) and `Body%` (1.6%, need
≥70%). Both are arguably measuring the wrong thing for how this pipeline actually turned out:
- `Min%`: this corpus is ~99.98% GDELT (day-precision by nature — see CLAUDE.md's own
  invariant). A 60% minute-precision threshold assumes an RSS-heavy corpus that this isn't.
- `Body%`: computed against the *full* 546k-article corpus, but body-fetch was deliberately
  run `--verified-only` (9,795 articles, 87.1% success). The denominator is stale relative to
  that design choice.
I left both thresholds untouched — whether to lower them, redefine the denominators, or
decide the current data genuinely isn't sufficient is a real feasibility judgment call, not
a coding bug.

## 4. Environment left running-ready
`ssh bouchet` works via `ControlMaster` multiplexing (see `reports/bouchet_login_howto.md`) —
one Duo approval per ~2h session, no browser automation needed anymore. `uv sync` complete,
`.venv` live under `/nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket`. Re-run anything
with:
```bash
ssh bouchet
cd /nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket
sbatch scripts/bouchet/run_pipeline_08_to_14.sbatch   # idempotent, skips completed steps
```
