# Polymarket News Shock Thesis Pipeline

> **LLM Agent Note:** This file documents architecture for debugging and new feature work. Read it fully before touching any code.

---

## What This Is

**Direction 4 — News Shock Embeddings and Architecture Comparison in Prediction Markets.**

A 14-script research data pipeline that:
1. Collects resolved Polymarket prediction market trade histories across sports, politics, and geopolitics.
2. Assembles a timestamped news corpus from GDELT + category RSS feeds.
3. Matches news articles to markets (BGE-large FAISS → LLM verification).
4. Computes log-odds reaction windows and market characteristics for each verified article.
5. Runs a per-category purging regression to produce **news shock embeddings** — the residual from predicting an article's analysis embedding using observable market state.

The deliverable is `data/analysis/shock_embeddings.parquet`: one shock embedding per verified article, ready for Weeks 4–6 architecture training (linear baseline, LSTM, transformer, TCN) across three event categories.

---

## Stack

- **Language:** Python 3.11+
- **Package manager:** uv
- **Key libraries:** httpx, pydantic, duckdb, faiss-cpu, sentence-transformers, anthropic, google-cloud-bigquery, feedparser, trafilatura, scikit-learn, pandera

---

## Directory Structure

```
thesis/
├── Makefile                    # Orchestrates all 14 pipeline scripts
├── pyproject.toml
├── CLAUDE.md
├── config/
│   ├── categories.yaml         # Category → Polymarket tags + feed URLs
│   ├── focal.yaml              # Date windows, market count targets per category
│   ├── analysis.yaml           # Analysis embedding model, reaction windows, ridge CV params
│   ├── credentials.yaml.template
│   └── paths.yaml              # All data directory paths
├── src/
│   ├── polymarket/             # Gamma API, Goldsky subgraph, trade normalization, resampler
│   ├── news/                   # GDELT BigQuery, category feeds, article fetcher, normalizer
│   ├── matching/               # BGE embedder, FAISS, candidate finder, LLM verifier, dedup
│   ├── analysis/               # Reaction windows, market chars, purging regression
│   ├── schemas/                # Pydantic models: Market, Trade, Article, NewsEvent, VerifiedArticle
│   └── utils/                  # Cache, rate limiter, DuckDB IO, logging
├── scripts/                    # 01_discover_universe.py … 14_feasibility_gate.py
├── data/                       # gitignored — all pipeline outputs
├── tests/
└── notebooks/
```

---

## Key Entry Points

| File | Role |
|------|------|
| `Makefile` | `make focal` runs the full pipeline end-to-end |
| `scripts/01_discover_universe.py` | Entry point — builds `data/polymarket/universe.parquet` |
| `scripts/14_feasibility_gate.py` | Exit gate — fails loudly if data density thresholds are not met |
| `src/schemas/verified_article.py` | Defines the primary deliverable schema (one row per verified article) |
| `src/analysis/purging.py` | Purging regression: `e_i = B·x_{k,t_i} + ε_i`; ε̂ = shock embedding |

---

## Two Embedding Passes (do not confuse)

| Purpose | Class | Model | Dim | dtype | Input |
|---------|-------|-------|-----|-------|-------|
| **Matching** | `BGEEmbedder` | `BAAI/bge-large-en-v1.5` | 1024 | float16 | title + lede |
| **Analysis** | `AnalysisEmbedder` | `intfloat/e5-large-v2` | 768 | float32 | title + lede + body_text |

The matching embedding is used only for FAISS candidate retrieval (script 07+08). The analysis embedding is used in the purging regression and architecture training (scripts 11, 13).

---

## Data Flow

```
Gamma API   ──► universe.parquet
Goldsky     ──► trades/ (partitioned Parquet, log-odds prices)
             ──► bars_1min/ (1-min LOCF bars; ts_min, close_lo, volume_usdc)
GDELT BQ    ──► news/gdelt_gkg/ (timestamp_precision="day")
ESPN/RSS    ──► news/feeds/    (timestamp_precision="minute")
trafilatura ──► news/bodies/{article_id}.txt
             ──► news/matching_embeddings/ (BGE-large float16 + FAISS index)
Claude Haiku──► matches.db  (candidates → verifications → news_events)
             ──► news/analysis_embeddings/ (E5-large float32)
             ──► analysis/tuples.parquet   (VerifiedArticle rows)
             ──► analysis/shock_embeddings.parquet  (primary deliverable)
```

---

## Conventions

- All prices in model-facing fields are log-odds (`float`); raw [0,1] prices stored as `price_raw` only
- Reaction windows are computed in log-odds: `y_logit_Δ = logit(P_{k,t+Δ}) − logit(P_{k,t})`
- `timestamp_precision` on every article: `"minute"` | `"day"` | `"unknown"`
- `body_text_available: bool` on every Article
- `embedding_source: Literal["full_text","headline_only"]` on every VerifiedArticle
- Parquet partitioning: `category=<cat>/year=<Y>/month=<M>/part-*.parquet`
- Every script writes a `_SUCCESS` marker on completion; Makefile checks these
- Purging regression always uses out-of-sample residuals for val/test splits

---

## Known Constraints / Gotchas

- Do not use CLOB `/prices-history` — broken for resolved markets (see CLAUDE.md)
- Do not treat GDELT SEENDATE as publication time
- GDELT timestamp always `"day"` precision — never override this
- Matching embeddings (BGE) and analysis embeddings (E5) serve different purposes; do not mix them
- Goldsky timestamps are integer seconds; `log_index` is a tiebreaker, not sub-second time
- `price_raw` of exactly 0.0 or 1.0 → clip to (0.001, 0.999) before log-odds conversion
