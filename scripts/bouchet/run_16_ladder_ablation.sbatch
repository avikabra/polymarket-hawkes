#!/bin/bash
#SBATCH --job-name=16-ladder-abl
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_16_ladder_%j.out
#SBATCH --error=logs/bouchet_16_ladder_%j.err

# Head-to-head ablation (novel_math_design.md item 1): does training script
# 16's ridge baseline against the isotonic ladder-corrected target
# (y_logit_24h_ladder) improve val/test error over the raw y_logit_24h
# target, on price_ladder (the category the design doc names as the
# primary beneficiary — real ladders of 53-59 strikes). CPU-bound (small
# ridge fit); gpu partition used only because it schedules faster here.

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876

module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"

cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
echo "=== y_logit_24h (unadjusted) ==="
uv run python scripts/16_train_linear_baseline.py --category price_ladder --embedding shock --target y_logit_24h
echo
echo "=== y_logit_24h_ladder (isotonic-corrected) ==="
uv run python scripts/16_train_linear_baseline.py --category price_ladder --embedding shock --target y_logit_24h_ladder
