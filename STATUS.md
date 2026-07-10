# Week 1–3 Status — Polymarket News Shock Pipeline (Direction 4)

> Checkpoint: 2026-07-10. All code is committed and pushed; the live-run chain is partially complete.

---

## Design of Record

**README.md is authoritative.** This is a 14-script *news-shock-embeddings* pipeline (Direction 4).

The file `cc_prompts_thesis_pipeline.md` (untracked) describes the old 11-script *bivariate Hawkes*
design and is stale — ignore it. The GitHub remote is still named `polymarket-hawkes` (historical).

---

## Code Status

All 14 scripts and all `src/` modules are implemented. No stubs, no `NotImplementedError`.

| Component | Files | Status |
|-----------|-------|--------|
| Schemas | `src/schemas/` — Market, Trade, Article, NewsEvent, VerifiedArticle | ✅ Complete |
| Polymarket data | `src/polymarket/` — Gamma, Goldsky, resampler | ✅ Complete |
| News corpus | `src/news/` — GDELT BigQuery, ESPN/RSS/NBA feeds, normalizer, fetcher | ✅ Complete |
| Matching | `src/matching/` — BGEEmbedder, AnalysisEmbedder, candidate_finder, llm_verifier, dedup, faiss | ✅ Complete |
| Analysis core | `src/analysis/` — market_chars, reaction_windows, purging (D4 econometrics) | ✅ Complete |
| Scripts 01–14 | `scripts/` — full pipeline from discovery → shocks → gate | ✅ Complete |
| Tests | `tests/` — ~15 test files, all substantive | ✅ Complete |
| Config | `config/` — focal.yaml, paths.yaml, analysis.yaml, categories/ | ✅ Complete |
| Makefile | `Makefile` — `make focal` runs full pipeline end-to-end | ✅ Complete |

**Primary deliverable:** `data/analysis/shock_embeddings.parquet` (one 768-dim shock embedding per
verified article). Not yet produced — pipeline still needs to be run end-to-end.

---

## Live-Run Progress

Scripts 01–05 have been run and produced artifacts. Script 08 (`match_candidates`) has also been
run (`matches.db` exists). The body-fetch → verify → shocks chain has not been run.

| Script | Purpose | Run? | Artifact |
|--------|---------|------|---------|
| 01 `discover_universe` | Gamma market discovery | ✅ | `data/polymarket/universe.parquet` |
| 02 `pull_trades` | Goldsky trade fills | ✅ | `data/polymarket/trades/` + `_SUCCESS` |
| 03 `resample_trades` | 1-min OHLCV bars | ✅ | `data/polymarket/bars_1min/` + `_SUCCESS` |
| 04 `pull_gdelt_corpus` | GDELT GKG via BigQuery | ✅ | `data/news/gdelt_gkg/` + `_SUCCESS` |
| 05 `pull_category_feeds` | ESPN/RSS/NBA feeds | ✅ | `data/news/feeds/` + `_SUCCESS` |
| 06 `fetch_article_bodies` | Body-text via trafilatura | ❌ not run | `data/news/bodies/` |
| 07 `embed_for_matching` | BGE-large FAISS index | ❌ not run | `data/news/embeddings/matching.faiss` |
| 08 `match_candidates` | Top-K FAISS candidates | ✅ | `data/matches/matches.db` |
| 09 `llm_verify_matches` | Claude Haiku verification | ❌ not run | `matches.db::verifications` |
| 10 `dedup_into_events` | Cluster into NewsEvents | ❌ not run | `matches.db::news_events` |
| 11 `embed_for_analysis` | E5-large analysis embeds | ❌ not run | `data/news/embeddings/analysis/` |
| 12 `assemble_dataset` | VerifiedArticle dataset | ❌ not run | `data/analysis/dataset.parquet` |
| 13 `purge_and_compute_shocks` | Ridge purging → shocks | ❌ not run | `data/analysis/shock_embeddings.parquet` ⭐ |
| 14 `feasibility_gate` | Gate: fail if density < threshold | ❌ not run | stdout pass/fail |

---

## Remaining Weeks 1–3 Work

Run the pipeline end-to-end:

```bash
# Requires: ANTHROPIC_API_KEY and GOOGLE_APPLICATION_CREDENTIALS in .env
make focal          # runs scripts 01–14 in order, writes _SUCCESS markers
# or step-by-step:
uv run python scripts/06_fetch_article_bodies.py
uv run python scripts/07_embed_for_matching.py
uv run python scripts/09_llm_verify_matches.py   # needs ANTHROPIC_API_KEY
uv run python scripts/10_dedup_into_events.py
uv run python scripts/11_embed_for_analysis.py
uv run python scripts/12_assemble_dataset.py
uv run python scripts/13_purge_and_compute_shocks.py
uv run python scripts/14_feasibility_gate.py     # must pass to proceed to Week 4
```

**Gate thresholds (script 14):** ≥200 resolved markets/category; median ≥10 verified
articles/market; median ≥50 trades/market; ≥60% "minute"-precision articles; ≥70% with body text.

If the gate fails, diagnose which category falls short before proceeding.

---

## Weeks 4–6 (Future — not in this repo)

Architecture training and comparison, gated on script 14 passing:
- Linear baseline (ridge on shock embeddings)
- LSTM
- Transformer
- TCN

Input: `data/analysis/shock_embeddings.parquet` + `data/analysis/dataset.parquet`.
These will live in a separate repo or `src/models/` extension.

---

## Housekeeping Done (this checkpoint)

- Removed 5 stale `" 2"` duplicate files (old field name `text_available` vs current `body_text_available`):
  `src/matching/embedder 2.py`, `src/news/article_fetcher 2.py`, `src/news/feeds/nba_stats 2.py`,
  `tests/test_gdelt 2.py`, `config/paths 2.yaml`
- `cc_prompts_thesis_pipeline.md` left untracked (stale Hawkes spec, not part of D4)
