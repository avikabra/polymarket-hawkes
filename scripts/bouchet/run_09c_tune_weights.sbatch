#!/bin/bash
#SBATCH --job-name=09c-tune
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_09c_tune_%j.out
#SBATCH --error=logs/bouchet_09c_tune_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
uv run python scripts/09c_tune_matching_weights.py
