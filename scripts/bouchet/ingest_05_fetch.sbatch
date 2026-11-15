#!/bin/bash
#SBATCH --job-name=ingest05-fetch
#SBATCH --partition=day
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=23:00:00
#SBATCH --account=pi_btk22
#SBATCH --array=0-3
#SBATCH --output=logs/bouchet_ingest05_%A_%a.out
#SBATCH --error=logs/bouchet_ingest05_%A_%a.err

# Steps 17 and 18: fetch article text and recheck names. Task i of 4 takes the URLs whose hash falls
# in part i, with one connection per domain per task (at most 4 per domain overall). Finished chunks
# are skipped, so resubmitting the array resumes. Usage: sbatch scripts/bouchet/ingest_05_fetch.sbatch
# Needs data/news/gdelt_candidates under the working directory.

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
PY=$PROJECT_ROOT/thesis-polymarket/.venv/bin/python

cd "$PROJECT_ROOT/thesis-ingest"
mkdir -p logs

echo "Node: $(hostname)  task $SLURM_ARRAY_TASK_ID of 4"

$PY scripts/ingest/05_fetch_articles.py --part "$SLURM_ARRAY_TASK_ID" --parts 4
