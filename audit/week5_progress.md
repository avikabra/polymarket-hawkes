# Week 5 Progress

## Completed

- [ ] Script 17: `train_lstm.py` — LSTM/GRU with random hyperparameter search (n=12)
- [ ] Script 18: `train_transformer.py` — Transformer with time-decay attention and warmup
- [ ] Script 19: `train_tcn.py` — TCN with random hyperparameter search (n=10)
- [ ] Model checkpoints saved to `models/checkpoints/`
- [ ] Hyperparameter search logs saved to `models/hparam_search/`

LSTM and TCN implementations complete. Run scripts 17 and 19 on Colab GPU after linear baseline completes.

## In Progress

- [ ] Transformer training (script 18) — longer wall-clock time; monitor val loss curve
- [ ] Script 20: `evaluate_all_models.py` — pending all model checkpoints

## Blockers

- Scripts 17-19 must run on GPU (Colab); local CPU runs are infeasibly slow
- `results/metrics_all.parquet` (prerequisite for `make evaluate`) not yet available

## Next Steps

1. Complete GPU runs for all 4 architectures × 8 category/embedding combos
2. Run `make evaluate` once `results/metrics_all.parquet` is populated
3. Run script 21 (`hypothesis_tests.py`) to compute H1-H4 test statistics
4. Execute `make report` to render notebooks 05-07
5. Fill in `[PLACEHOLDER]` values in `reports/weeks_4_6_report.md`
