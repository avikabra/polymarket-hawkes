#!/bin/bash
#SBATCH --job-name=13-revenue-split-fix
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_13_revenue_split_fix_%j.out
#SBATCH --error=logs/bouchet_13_revenue_split_fix_%j.err

# 2026-10-13 decision: give revenue_ladder its own fallback split (its real
# resolution dates land almost entirely after the shared global cutoff, so it
# got 0 train rows under that cutoff -- see src/analysis/purging.py's new
# per-category fallback). Only reruns script 13 (purging) -- script 12's
# tuples.parquet doesn't need to change, the fallback logic is entirely
# inside purge_by_category.

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
uv run python scripts/13_purge_and_compute_shocks.py

echo "=== Sanity check: revenue_ladder split counts ==="
uv run python -c "
import pandas as pd
df = pd.read_parquet('data/analysis/shock_embeddings.parquet')
rev = df[df['category'] == 'revenue_ladder']
print('revenue_ladder total rows:', len(rev))
print(rev['split'].value_counts())
print('revenue_ladder valid_24h rows:', int(rev['valid_24h'].sum()))
"
