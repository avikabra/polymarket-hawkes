#!/bin/bash
#SBATCH --job-name=backfill-resolved
#SBATCH --partition=day
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_backfill_resolved_%j.out
#SBATCH --error=logs/bouchet_backfill_resolved_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
uv run python scripts/backfill_resolved_at.py \
    --in data/polymarket/universe.parquet.bak_preresolvedat \
    --out data/polymarket/universe.parquet
