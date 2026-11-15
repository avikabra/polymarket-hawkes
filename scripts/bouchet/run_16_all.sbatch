#!/bin/bash
#SBATCH --job-name=script16-all
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:45:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_16_all_%j.out
#SBATCH --error=logs/bouchet_16_all_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
for cat in all corporate_event price_ladder revenue_ladder valuation_ladder market_cap_ladder; do
  for emb in shock raw; do
    echo "--- category=$cat embedding=$emb ---"
    uv run python scripts/16_train_linear_baseline.py --category "$cat" --embedding "$emb" || echo "  (non-zero exit, likely no training data for $cat — continuing)"
  done
done
