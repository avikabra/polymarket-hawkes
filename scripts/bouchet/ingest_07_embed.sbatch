#!/bin/bash
#SBATCH --job-name=ingest07-embed
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_ingest07_%j.out
#SBATCH --error=logs/bouchet_ingest07_%j.err

# Steps 19 to 21: Qwen3-Embedding-4B on articles (resumes by shard).
# Usage: sbatch scripts/bouchet/ingest_07_embed.sbatch [batch_size]
# Needs data/news/articles.parquet under the working directory.

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
PY=$PROJECT_ROOT/thesis-polymarket/.venv/bin/python
export HF_HOME="$PROJECT_ROOT/.cache/huggingface"

cd "$PROJECT_ROOT/thesis-ingest"
mkdir -p logs

BATCH_SIZE="${1:-8}"
echo "Node: $(hostname)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

$PY scripts/ingest/07_embed.py --what articles --batch-size "$BATCH_SIZE"
