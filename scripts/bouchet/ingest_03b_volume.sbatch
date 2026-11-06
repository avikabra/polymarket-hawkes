#!/bin/bash
#SBATCH --job-name=ingest03b-volume
#SBATCH --partition=day
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_ingest03b_%j.out
#SBATCH --error=logs/bouchet_ingest03b_%j.err

# Step 6: daily dollars and shares per contract and the cumulative dollars through each day, from
# the pulled trades. Writes data/polymarket/daily_volume.parquet. Rerun after script 03 finishes.
# Usage: sbatch scripts/bouchet/ingest_03b_volume.sbatch

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
PY=$PROJECT_ROOT/thesis-polymarket/.venv/bin/python

cd "$PROJECT_ROOT/thesis-ingest"
mkdir -p logs

echo "Node: $(hostname)"

$PY scripts/ingest/03b_daily_volume.py
