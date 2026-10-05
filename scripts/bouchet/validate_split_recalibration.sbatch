#!/bin/bash
#SBATCH --job-name=validate-split
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_validate_split_%j.out
#SBATCH --error=logs/bouchet_validate_split_%j.err

# Confirms whether the 9/30 split recalibration (commit 456c5c8, train_before
# 2026-04-17 / val_range to 2026-06-10 / test_from 2026-06-10) actually fixes the
# train=2562/val=111/test=56395 skew reported in bouchet_overnight_run_status.md §3b,
# on a full rerun of scripts 12-14 against the post-backfill universe.parquet. This has
# never been checked — the recalibration commit only reasoned from quantiles of
# market_resolved_at, not from an actual rerun's split counts.

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876

module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"

cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
echo "=== Re-running scripts 12-14 so the split reflects the current config/analysis.yaml cutoffs ==="
uv run python scripts/12_assemble_dataset.py
uv run python scripts/13_purge_and_compute_shocks.py

echo "=== Split counts, overall and per category (valid_24h only) ==="
uv run python -c "
import pandas as pd
df = pd.read_parquet('data/analysis/shock_embeddings.parquet')
valid = df[df['valid_24h'] == True]
print('--- overall split counts (valid_24h) ---')
print(valid['split'].value_counts(dropna=False))
print()
print('--- per-category split counts (valid_24h) ---')
print(valid.groupby(['category', 'split']).size().unstack(fill_value=0))
print()
print('--- resolved_at null rate (should be ~0% post-backfill) ---')
u = pd.read_parquet('data/polymarket/universe.parquet')
print(f\"{u['resolved_at'].isna().mean():.2%} null, {len(u)} rows\")
"

echo "=== Feasibility gate, against this real post-recalibration data ==="
uv run python scripts/14_feasibility_gate.py
