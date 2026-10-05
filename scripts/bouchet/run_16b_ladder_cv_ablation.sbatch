#!/bin/bash
#SBATCH --job-name=16b-ladder-cv
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_16b_ladder_cv_%j.out
#SBATCH --error=logs/bouchet_16b_ladder_cv_%j.err

# The real version of the "fair test" for Thread 2 (out-of-fold CV, cohort-stratified
# folds) that run_16_ladder_ablation.sbatch's production-split comparison could not
# answer cleanly (see commit f372170). Never submitted to Bouchet before 2026-10-05 —
# the only existing results/ladder_cv_ablation.parquet was run locally against
# scripts/make_synthetic_shock_embeddings.py's 200-row synthetic fixture, not real data.
# This runs all 4 ladder categories against the real data/analysis/shock_embeddings.parquet
# (59,068 rows) in one invocation via --category all-ladder-categories (script default).

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876

module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"

cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
echo "=== Confirming shock_embeddings.parquet is the real 59,068-row file, not a local synthetic fixture ==="
uv run python -c "
import pandas as pd
df = pd.read_parquet('data/analysis/shock_embeddings.parquet')
print('rows:', len(df))
assert len(df) > 10000, 'this looks like the synthetic smoke fixture, not the real Bouchet output — abort'
print(df['category'].value_counts())
print(df['split'].value_counts())
"

echo "=== Running cohort-stratified CV ablation, all ladder categories ==="
uv run python scripts/16b_ladder_cv_ablation.py --category all-ladder-categories --embedding shock

echo "=== Result ==="
uv run python -c "
import pandas as pd
df = pd.read_parquet('results/ladder_cv_ablation.parquet')
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
print(df)
"
