#!/bin/bash
#SBATCH --job-name=script07-embed
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_script07_%j.out
#SBATCH --error=logs/bouchet_script07_%j.err

# Bouchet job for Script 07 (BGE-large matching embeddings).
# Usage: sbatch scripts/bouchet/07_embed_for_matching.sbatch [batch_size]
# See reports/bouchet_deferred_compute.md for context and verification steps.

set -euo pipefail

# Everything for this project lives under Kelly's PI project space, never under $HOME
# (home is private, mode 700 — invisible to the group). See reports/bouchet_login_howto.md §0.
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876

module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"

cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

BATCH_SIZE="${1:-256}"   # Start conservative on unfamiliar GPU/VRAM; the local MPS ceiling of
                          # 128 does NOT apply here (see reports/bouchet_deferred_compute.md).

echo "Node: $(hostname)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo "Batch size: $BATCH_SIZE"

uv run python scripts/07_embed_for_matching.py --batch-size "$BATCH_SIZE"

# Verify expected output cardinality (628 contract groups)
uv run python -c "
import pandas as pd
df = pd.read_parquet('data/news/matching_embeddings/group_embeddings.parquet')
assert len(df) == 628, f'expected 628 groups, got {len(df)}'
print('OK', df.shape)
"
