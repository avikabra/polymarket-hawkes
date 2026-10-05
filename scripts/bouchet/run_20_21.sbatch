#!/bin/bash
#SBATCH --job-name=eval-hyp
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_20_21_%j.out
#SBATCH --error=logs/bouchet_20_21_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Script 20: evaluate all models ==="
uv run python scripts/20_evaluate_all_models.py
echo
echo "=== Script 21: hypothesis tests ==="
uv run python scripts/21_hypothesis_tests.py
