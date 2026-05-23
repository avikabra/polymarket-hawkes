# Polymarket Hawkes Thesis Pipeline

> **LLM Agent Note:** This file documents architecture for debugging and new feature work. Read it fully before touching any code.

---

## What This Is

A three-stage research data pipeline that (1) collects resolved Polymarket prediction market trade histories, (2) assembles a timestamped news corpus from GDELT + category feeds, and (3) matches news events to markets to produce a dataset of `(market, log-odds price series, matched news events)` tuples for bivariate Hawkes process fitting.

---

## Stack

- **Language:** Python 3.12
- **Package manager:** uv
- **Key libraries:** httpx, pydantic, duckdb, faiss-cpu, sentence-transformers, anthropic, google-cloud-bigquery, feedparser, trafilatura, pandera

---

## Directory Structure
thesis/
├── Makefile                    # Orchestrates all 11 pipeline scripts
├── pyproject.toml
├── CLAUDE.md
├── config/
│   ├── categories.yaml         # Category → Polymarket tags + feed URLs
│   ├── focal.yaml              # Week 4–6 NFL/NBA season-long scope
│   ├── credentials.yaml.template
│   └── paths.yaml              # All data directory paths
├── src/
│   ├── polymarket/             # Gamma API, Goldsky subgraph, trade normalization
│   ├── news/                   # GDELT BigQuery, category feeds, normalizer
│   ├── matching/               # Embedder, FAISS, LLM verifier, deduplication
│   ├── schemas/                # Pydantic models for every data type
│   └── utils/                  # Cache, rate limiter, DuckDB IO, logging
├── scripts/                    # 01_discover_universe.py … 11_feasibility_gate.py
├── data/                       # gitignored — all pipeline outputs
├── tests/
└── notebooks/

---

## Key Entry Points

| File | Role |
|------|------|
| `Makefile` | `make focal` runs the full pipeline; individual targets per script |
| `scripts/01_discover_universe.py` | Entry point — builds `data/polymarket/universe.parquet` |
| `scripts/11_feasibility_gate.py` | Exit gate — fails loudly if data density is insufficient for Hawkes fitting |
| `src/schemas/analysis_tuple.py` | Defines the final deliverable schema |

---

## Data Flow
Gamma API ──► universe.parquet
Goldsky   ──► trades/ (partitioned Parquet, log-odds prices)
          ──► bars_1min/ (resampled)
GDELT BQ  ──► news/gdelt_gkg/ (timestamp_precision="day")
ESPN/RSS  ──► news/feeds/    (timestamp_precision="minute")
          ──► embeddings/ (BGE-large float16 + FAISS index)
          ──► matches.db  (SQLite: candidates → verifications → news_events)
          ──► analysis/tuples.parquet  (final deliverable)

---

## Conventions

- All prices in model-facing fields are log-odds (`float`); raw [0,1] prices stored separately as `price_raw`
- `timestamp_precision` field on every article and news_event: `"minute"` | `"day"` | `"unknown"`
- `included_in_hawkes_likelihood: bool` on every NewsEvent — True only when `timestamp_precision == "minute"`
- Parquet partitioning: `category=<cat>/year=<Y>/month=<M>/part-*.parquet`
- Every script writes a `_SUCCESS` marker on completion; Makefile checks these

---

## Known Constraints / Gotchas

- Do not use CLOB `/prices-history` — broken for resolved markets (see CLAUDE.md)
- Do not treat GDELT SEENDATE as publication time
- Do not set `included_in_hawkes_likelihood=True` for any GDELT-only timestamp
- Do not modify `data/` contents manually — always regenerate via scripts
