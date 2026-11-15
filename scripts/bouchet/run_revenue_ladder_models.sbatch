#!/bin/bash
#SBATCH --job-name=revenue-ladder-models
#SBATCH --partition=gpu_devel
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_revenue_ladder_models_%j.out
#SBATCH --error=logs/bouchet_revenue_ladder_models_%j.err

# 2026-10-13: revenue_ladder never had a trained model at all (0 train rows
# under the old shared global split). Run AFTER run_13_revenue_split_fix.sbatch
# confirms it now has real train rows. Trains all four architectures for this
# one category, mirroring the existing per-category jobs
# (run_lstm_price_ladder.sbatch etc.) -- --device cpu even on the gpu_devel
# partition, same as those, since this is small-data CPU-bound training that
# just schedules faster here.

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="

echo "=== Linear baseline, raw embedding ==="
uv run python scripts/16_train_linear_baseline.py --category revenue_ladder --embedding raw

echo "=== Linear baseline, shock embedding ==="
uv run python scripts/16_train_linear_baseline.py --category revenue_ladder --embedding shock

echo "=== LSTM ==="
uv run python scripts/17_train_lstm.py --category revenue_ladder --embedding shock --device cpu

echo "=== Transformer ==="
uv run python scripts/18_train_transformer.py --category revenue_ladder --embedding shock --device cpu

echo "=== TCN ==="
uv run python scripts/19_train_tcn.py --category revenue_ladder --embedding shock --device cpu

echo "=== Re-evaluate everything (existing checkpoints + new revenue_ladder ones) ==="
uv run python scripts/20_evaluate_all_models.py

echo "=== Rerun H1-H4 with revenue_ladder now in the picture ==="
uv run python scripts/21_hypothesis_tests.py
