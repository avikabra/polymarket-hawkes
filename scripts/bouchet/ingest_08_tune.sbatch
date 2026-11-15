#!/bin/bash
#SBATCH --job-name=ingest08-tune
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_ingest08tune_%j.out
#SBATCH --error=logs/bouchet_ingest08tune_%j.err

# Tuning the matching instructions: answers tune/sample400.parquet with every variant in tune/variants/ not yet run.
#   sbatch scripts/bouchet/ingest_08_tune.sbatch

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
PY=$PROJECT_ROOT/thesis-ingest/.venv-llm/bin/python
module load CUDA
export PATH="$PROJECT_ROOT/thesis-ingest/.venv-llm/bin:$PATH"
export VLLM_USE_FLASHINFER_SAMPLER=0  # greedy decoding needs no compiled sampler
export HF_HOME="$PROJECT_ROOT/.cache/huggingface"

cd "$PROJECT_ROOT/thesis-ingest"
mkdir -p logs

echo "Node: $(hostname)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

$PY scripts/ingest/08_tune.py --run "$@"
