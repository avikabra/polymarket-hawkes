PYTHON       := uv run python
FOCAL_CONFIG := config/focal.yaml

.PHONY: all focal audit clean

all: focal

focal: data/analysis/_FOCAL_SUCCESS

# ── Polymarket pipeline ────────────────────────────────────────────────────────

data/polymarket/universe.parquet:
	$(PYTHON) scripts/01_discover_universe.py --config $(FOCAL_CONFIG)

data/polymarket/trades/_SUCCESS: data/polymarket/universe.parquet
	$(PYTHON) scripts/02_pull_trades.py

data/polymarket/bars_1min/_SUCCESS: data/polymarket/trades/_SUCCESS
	$(PYTHON) scripts/03_resample_trades.py

# ── News corpus ────────────────────────────────────────────────────────────────

data/news/gdelt_gkg/_SUCCESS: data/polymarket/universe.parquet
	$(PYTHON) scripts/04_pull_gdelt_corpus.py --config $(FOCAL_CONFIG)

data/news/feeds/_SUCCESS: data/polymarket/universe.parquet
	$(PYTHON) scripts/05_pull_category_feeds.py --config $(FOCAL_CONFIG)

# Body text — critical path; blocks analysis embeddings
data/news/bodies/_SUCCESS: data/news/gdelt_gkg/_SUCCESS data/news/feeds/_SUCCESS
	$(PYTHON) scripts/06_fetch_article_bodies.py

# ── Matching pipeline (BGE-large only) ────────────────────────────────────────

data/news/matching_embeddings/_SUCCESS: data/news/bodies/_SUCCESS
	$(PYTHON) scripts/07_embed_for_matching.py

data/matches/_CANDIDATES_SUCCESS: data/news/matching_embeddings/_SUCCESS
	$(PYTHON) scripts/08_match_candidates.py

data/matches/_VERIFIED_SUCCESS: data/matches/_CANDIDATES_SUCCESS
	$(PYTHON) scripts/09_llm_verify_matches.py

data/matches/_EVENTS_SUCCESS: data/matches/_VERIFIED_SUCCESS
	$(PYTHON) scripts/10_dedup_into_events.py

# ── Analysis embeddings (verified articles only) ───────────────────────────────

data/news/analysis_embeddings/_SUCCESS: data/matches/_VERIFIED_SUCCESS data/news/bodies/_SUCCESS
	$(PYTHON) scripts/11_embed_for_analysis.py

# ── Assembly + purging ─────────────────────────────────────────────────────────

data/analysis/tuples.parquet: data/polymarket/bars_1min/_SUCCESS \
                               data/matches/_EVENTS_SUCCESS \
                               data/news/analysis_embeddings/_SUCCESS
	$(PYTHON) scripts/12_assemble_dataset.py

data/analysis/shock_embeddings.parquet: data/analysis/tuples.parquet
	$(PYTHON) scripts/13_purge_and_compute_shocks.py

data/analysis/_FOCAL_SUCCESS: data/analysis/shock_embeddings.parquet
	$(PYTHON) scripts/14_feasibility_gate.py

# ── Audits ─────────────────────────────────────────────────────────────────────

audit: data/analysis/_FOCAL_SUCCESS
	$(PYTHON) scripts/audit_news_coverage.py

# ── Housekeeping ───────────────────────────────────────────────────────────────

clean:
	rm -rf data/
