#!/bin/bash
#SBATCH --job-name=fix-parent-event
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_fix_parent_event_%j.out
#SBATCH --error=logs/bouchet_fix_parent_event_%j.err

# Full chain to make H1-H4's bootstrap CIs real: backfill parent_event_id (was
# hardcoded None -- see src/polymarket/gamma.py's 2026-10-10 fix), then rerun
# only the stages that actually need to see it. No retraining: script 20 just
# re-evaluates the existing checkpoints in models/checkpoints/ against the
# corrected data.

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="

echo "=== Step 1/4: backfill parent_event_id ==="
cp data/polymarket/universe.parquet data/polymarket/universe.parquet.bak_preparenteventid
uv run python scripts/backfill_parent_event_id.py

echo "=== Step 2/4: script 13 (rejoin parent_event_id into shock_embeddings.parquet) ==="
uv run python scripts/13_purge_and_compute_shocks.py

echo "=== Step 3/4: script 20 (re-evaluate existing checkpoints, no retraining) ==="
uv run python scripts/20_evaluate_all_models.py

echo "=== Step 4/4: script 21 (real bootstrap CIs, H1-H4 rerun) ==="
uv run python scripts/21_hypothesis_tests.py

echo "=== Sanity check: parent_event_id cluster count in the final test predictions ==="
uv run python -c "
import pandas as pd
df = pd.read_parquet('results/test_predictions.parquet')
print('unique parent_event_id values:', df['parent_event_id'].fillna('').astype(str).nunique())
print('rows with non-empty parent_event_id:', (df['parent_event_id'].fillna('').astype(str) != '').sum(), '/', len(df))
"
