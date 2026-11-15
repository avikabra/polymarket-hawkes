#!/bin/bash
#SBATCH --job-name=ingest08-scan
#SBATCH --partition=day
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_ingest08scan_%j.out
#SBATCH --error=logs/bouchet_ingest08scan_%j.err

# CPU step before the GPU matching job: scans every fetch shard for name hits and writes
# data/news/company_map/<prompt_version>/questions.parquet (one row per article, full text), so the GPU job only answers.
#   sbatch scripts/bouchet/ingest_08_scan.sbatch

set -euo pipefail
cd /nfs/roberts/project/pi_btk22/ak2876/thesis-ingest
mkdir -p logs
../thesis-polymarket/.venv/bin/python scripts/ingest/08_map_companies.py --scan
