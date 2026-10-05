#!/bin/bash
#SBATCH --job-name=item1-tcn-price_ladder
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_item1_tcn_price_ladder_%j.out
#SBATCH --error=logs/bouchet_item1_tcn_price_ladder_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
uv run python scripts/19_train_tcn.py --category price_ladder --embedding shock --device cpu
