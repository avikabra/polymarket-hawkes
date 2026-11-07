#!/bin/bash
#SBATCH --job-name=ingest08-map
#SBATCH --partition=gpu
#SBATCH --gpus=l40s:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=1-00:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_ingest08_%j.out
#SBATCH --error=logs/bouchet_ingest08_%j.err

# Company matching with Qwen3.5-4B on vLLM: one yes/no question per (article, company) pair, about 1.2 million
# pairs at about 25 pairs/s (13 to 14 h). Resumes at the first missing chunk, so resubmit if the time limit hits.
# Arguments go to the script:
#   sbatch scripts/bouchet/ingest_08_map.sbatch --limit 1000
#   sbatch scripts/bouchet/ingest_08_map.sbatch
#   sbatch scripts/bouchet/ingest_08_map.sbatch --retry
#   sbatch scripts/bouchet/ingest_08_map.sbatch --build
# Reads the questions written by ingest_08_scan.sbatch (run that first). Needs the env from setup_llm_env.sh.

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

$PY scripts/ingest/08_map_companies.py "$@"
