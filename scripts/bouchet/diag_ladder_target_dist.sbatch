#!/bin/bash
#SBATCH --job-name=diag-ladder-dist
#SBATCH --partition=devel
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:10:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_diag_ladder_dist_%j.out
#SBATCH --error=logs/bouchet_diag_ladder_dist_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

uv run python -c "
import pandas as pd
import numpy as np
df = pd.read_parquet('data/analysis/shock_embeddings.parquet')
sub = df[(df['valid_24h'] == True) & (df['category'] == 'price_ladder')]
for split in ['train','val','test']:
    s = sub[sub['split']==split]
    y1 = s['y_logit_24h']
    y2 = s['y_logit_24h_ladder']
    print(f'--- {split} (n={len(s)}) ---')
    print('y_logit_24h        : mean=%.4f std=%.4f min=%.4f max=%.4f' % (y1.mean(), y1.std(), y1.min(), y1.max()))
    print('y_logit_24h_ladder : mean=%.4f std=%.4f min=%.4f max=%.4f' % (y2.mean(), y2.std(), y2.min(), y2.max()))
    print('ladder_n_members_used_24h stats:', s['ladder_n_members_used_24h'].describe().to_dict())
"
