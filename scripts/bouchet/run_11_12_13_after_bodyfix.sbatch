#!/bin/bash
#SBATCH --job-name=11-12-13
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_11_12_13_%j.out
#SBATCH --error=logs/bouchet_11_12_13_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
echo "=== Script 11: analysis embeddings (picks up the 17 recovered bodies) ==="
uv run python scripts/11_embed_for_analysis.py
echo
echo "=== Script 12: assemble dataset ==="
uv run python scripts/12_assemble_dataset.py
echo
echo "=== Script 13: purge and compute shocks ==="
uv run python scripts/13_purge_and_compute_shocks.py
