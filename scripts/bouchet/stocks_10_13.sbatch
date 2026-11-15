#!/bin/bash
#SBATCH --job-name=stocks10-13
#SBATCH --partition=day
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_stocks10_13_%j.out
#SBATCH --error=logs/bouchet_stocks10_13_%j.err

# Section 6-7 inputs that need no matching: stock pull (10), characteristics (11), reactions (13), one after another.
#   sbatch scripts/bouchet/stocks_10_13.sbatch

set -euo pipefail
cd /nfs/roberts/project/pi_btk22/ak2876/thesis-ingest
mkdir -p logs
PY=../thesis-polymarket/.venv/bin/python
$PY scripts/ingest/10_pull_stocks.py
$PY scripts/ingest/11_characteristics.py
$PY scripts/ingest/13_reaction.py
