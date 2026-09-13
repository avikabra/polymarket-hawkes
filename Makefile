PYTHON       := uv run python

.PHONY: all focal audit train evaluate report test smoke clean

all: focal

focal: data/analysis/_FOCAL_SUCCESS

# ── Polymarket pipeline ────────────────────────────────────────────────────────

data/polymarket/universe.parquet:
	$(PYTHON) scripts/01_discover_universe.py

data/polymarket/trades/_SUCCESS: data/polymarket/universe.parquet
	$(PYTHON) scripts/02_pull_trades.py

data/polymarket/bars_1min/_SUCCESS: data/polymarket/trades/_SUCCESS
	$(PYTHON) scripts/03_resample_trades.py

# ── News corpus ────────────────────────────────────────────────────────────────

data/news/gdelt_gkg/_SUCCESS: data/polymarket/universe.parquet
	$(PYTHON) scripts/04_pull_gdelt_corpus.py

data/news/feeds/_SUCCESS: data/polymarket/universe.parquet
	$(PYTHON) scripts/05_pull_category_feeds.py

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

# ── Week 4-6 targets ─────────────────────────────────────────────────────────

train: data/analysis/_FOCAL_SUCCESS
	$(PYTHON) scripts/15_build_sequence_dataset.py
	$(PYTHON) scripts/16_train_linear_baseline.py --category all --embedding shock
	$(PYTHON) scripts/16_train_linear_baseline.py --category all --embedding raw
	$(PYTHON) scripts/16_train_linear_baseline.py --category sports --embedding shock
	$(PYTHON) scripts/16_train_linear_baseline.py --category sports --embedding raw
	$(PYTHON) scripts/16_train_linear_baseline.py --category politics --embedding shock
	$(PYTHON) scripts/16_train_linear_baseline.py --category politics --embedding raw
	$(PYTHON) scripts/16_train_linear_baseline.py --category geopolitics --embedding shock
	$(PYTHON) scripts/16_train_linear_baseline.py --category geopolitics --embedding raw
	@echo "Linear baseline complete. Run scripts 17-19 manually on GPU (Colab)."
	touch models/_TRAIN_LINEAR_SUCCESS

evaluate: results/metrics_all.parquet
	$(PYTHON) scripts/20_evaluate_all_models.py
	$(PYTHON) scripts/21_hypothesis_tests.py
	touch results/_EVALUATE_SUCCESS

report: results/_EVALUATE_SUCCESS
	jupyter nbconvert --to notebook --execute notebooks/05_baseline_performance.ipynb
	jupyter nbconvert --to notebook --execute notebooks/06_architecture_comparison.ipynb
	jupyter nbconvert --to notebook --execute notebooks/07_news_type_decomposition.ipynb

# ── Testing and smoke-testing ─────────────────────────────────────────────────

# Run W4-6 unit tests (no data or heavy models required).
# W1-3 tests (test_embedder.py etc.) load the BGE model which triggers a BLAS
# teardown segfault on Intel Mac when run together — they are excluded here.
W46_TESTS := tests/test_bootstrap.py tests/test_dataset.py \
             tests/test_forward.py tests/test_hparam_search.py \
             tests/test_lstm.py tests/test_metrics.py \
             tests/test_positional_encoding.py tests/test_purging.py \
             tests/test_tcn.py tests/test_trainer.py tests/test_transformer.py

test:
	uv run pytest $(W46_TESTS) -q

# End-to-end smoke test: generate synthetic data, run scripts 15/16/20/21, then clean up.
# Verifies the full pipeline wiring without real W1-3 data.
smoke:
	$(PYTHON) scripts/make_synthetic_shock_embeddings.py \
	    --out data/analysis/shock_embeddings.parquet --n 600 --seed 42
	$(PYTHON) scripts/15_build_sequence_dataset.py
	$(PYTHON) scripts/16_train_linear_baseline.py --category all --embedding shock
	$(PYTHON) scripts/16_train_linear_baseline.py --category all --embedding raw
	$(PYTHON) scripts/20_evaluate_all_models.py
	$(PYTHON) scripts/21_hypothesis_tests.py
	@echo "Smoke test complete. Cleaning up synthetic data..."
	rm -f data/analysis/shock_embeddings.parquet
	rm -rf models/checkpoints models/_TRAIN_LINEAR_SUCCESS results/

# ── Housekeeping ───────────────────────────────────────────────────────────────

clean:
	rm -rf data/
