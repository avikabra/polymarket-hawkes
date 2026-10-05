#!/bin/bash
#SBATCH --job-name=diag-dist2
#SBATCH --partition=devel
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_diag_dist2_%j.out
#SBATCH --error=logs/bouchet_diag_dist2_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

uv run python -c "
import pandas as pd
df = pd.read_parquet('data/analysis/tuples.parquet', columns=['market_resolved_at','category'])
df['market_resolved_at'] = pd.to_datetime(df['market_resolved_at'], utc=True, errors='coerce')
print('n rows:', len(df))
print('n null market_resolved_at:', df['market_resolved_at'].isna().sum())
s = df['market_resolved_at'].dropna()
print('min:', s.min(), 'max:', s.max())
for q in [0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]:
    print(f'  q{q}:', s.quantile(q))
print()
print('per-category date range + row-weighted quantiles:')
for cat, g in df.groupby('category'):
    gs = g['market_resolved_at'].dropna()
    if len(gs)==0:
        print(cat, 'n=0, no dates')
        continue
    print(cat, 'n=', len(gs), 'min=', gs.min(), 'q33=', gs.quantile(0.33), 'q66=', gs.quantile(0.66), 'max=', gs.max())
"
