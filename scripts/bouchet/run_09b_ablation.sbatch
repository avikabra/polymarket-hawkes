#!/bin/bash
#SBATCH --job-name=09b-ablation
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_09b_%j.out
#SBATCH --error=logs/bouchet_09b_%j.err

# Thread 1's required acceptance artifact (novel_math_design.md). CPU-bound
# (bars I/O + reaction-window computation over ~27k verified pairs) — same
# resource shape as script 12, which ran fine in this allocation. gpu
# partition used only because it schedules faster than pure-CPU partitions
# on this cluster right now, not because this step needs a GPU.

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876

module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"

cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
uv run python scripts/09b_matching_ablation.py
