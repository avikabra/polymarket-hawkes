# Week 4 Progress

## Completed

- [ ] Script 15: `build_sequence_dataset.py` — sequence dataset construction
- [ ] Script 16: `train_linear_baseline.py` — Ridge regression with cross-validated alpha selection
- [ ] `config/training.yaml` — training hyperparameters scaffold
- [ ] `config/paths.yaml` — extended with models/results/reports/audit sections
- [ ] Makefile `train` target
- [ ] Notebooks 05-07 scaffolded

Linear baseline code complete. Run `make train` after data pipeline completes.

## In Progress

- [ ] Data pipeline (`make focal`) — prerequisite for `make train`
- [ ] GPU environment setup on Colab for scripts 17-19

## Blockers

- `make train` depends on `data/analysis/_FOCAL_SUCCESS` from the weeks 1-3 pipeline
- Scripts 17 (LSTM), 18 (Transformer), 19 (TCN) require GPU; not runnable locally

## Next Steps

1. Verify `make focal` completes successfully and inspect `data/analysis/shock_embeddings.parquet`
2. Run `make train` to execute script 15 and all linear baseline variants
3. Upload `data/` outputs to Colab for GPU training (scripts 17-19)
4. Spot-check sequence dataset shape and split counts against plan §4 targets
