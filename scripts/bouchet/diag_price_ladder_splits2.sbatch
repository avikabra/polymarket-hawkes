#!/bin/bash
#SBATCH --job-name=diag-pl2
#SBATCH --partition=devel
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_diag_pl2_%j.out
#SBATCH --error=logs/bouchet_diag_pl2_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

uv run python -c "
import pandas as pd
df = pd.read_parquet('data/analysis/shock_embeddings.parquet')
sub = df[df['valid_24h'] == True]
sub = sub[sub['category'] == 'price_ladder']
print('price_ladder valid_24h split counts:')
print(sub['split'].value_counts(dropna=False))
"
