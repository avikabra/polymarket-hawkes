#!/bin/bash
#SBATCH --job-name=16b-ladder-cv
#SBATCH --partition=devel
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_16b_ladder_cv_%j.out
#SBATCH --error=logs/bouchet_16b_ladder_cv_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
uv run python scripts/16b_ladder_cv_ablation.py --category all-ladder-categories --n-splits 5
