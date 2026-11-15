#!/bin/bash
#SBATCH --job-name=ingest04-gdelt
#SBATCH --partition=day
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --account=pi_btk22
#SBATCH --array=0-57%6
#SBATCH --output=logs/bouchet_ingest04_%A_%a.out
#SBATCH --error=logs/bouchet_ingest04_%A_%a.err

# Steps 14 to 16: one task per month, 36 training months then 22 contract months, 6 at once.
# Each task streams its month's GKG files through memory; nothing raw is stored. Finished
# months are skipped, so resubmitting the array resumes. Usage: sbatch scripts/bouchet/ingest_04_gdelt.sbatch
# Needs data/polymarket/contracts/markets.parquet under the working directory (contract months).

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
PY=$PROJECT_ROOT/thesis-polymarket/.venv/bin/python

cd "$PROJECT_ROOT/thesis-ingest"
mkdir -p logs

MONTHS=()
for y in 2022 2023 2024; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do MONTHS+=("training $y-$m"); done; done
for y in 2025 2026; do for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
  if [ "$y-$m" \< "2026-11" ]; then MONTHS+=("contract $y-$m"); fi
done; done

read -r PERIOD MONTH <<< "${MONTHS[$SLURM_ARRAY_TASK_ID]}"
echo "Node: $(hostname)  task $SLURM_ARRAY_TASK_ID: $PERIOD $MONTH"

$PY "$PROJECT_ROOT/thesis-ingest/scripts/ingest/04_pull_gdelt.py" --month "$MONTH" --period "$PERIOD" --workers 4
