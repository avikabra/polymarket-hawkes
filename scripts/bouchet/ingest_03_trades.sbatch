#!/bin/bash
#SBATCH --job-name=ingest03-trades
#SBATCH --partition=day
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=23:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_ingest03_%j.out
#SBATCH --error=logs/bouchet_ingest03_%j.err

# Pull the trades of every non-excluded rung with any volume, from its start to its actual end.
# Resumable: finished part files are reused and cached API pages are kept, so if the job hits the
# 23h limit, resubmit it and it continues. Usage: sbatch scripts/bouchet/ingest_03_trades.sbatch
# Needs data/polymarket/contracts/markets.parquet under the working directory (script 02 output).

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
PY=$PROJECT_ROOT/thesis-polymarket/.venv/bin/python

cd "$PROJECT_ROOT/thesis-ingest"
mkdir -p logs

echo "Node: $(hostname)"

$PY scripts/ingest/03_pull_trades.py
