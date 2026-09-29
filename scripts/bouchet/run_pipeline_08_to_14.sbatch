#!/bin/bash
#SBATCH --job-name=pipeline-08-14
#SBATCH --partition=gpu
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_pipeline_%j.out
#SBATCH --error=logs/bouchet_pipeline_%j.err

# Runs scripts 08 through 14 in dependency order (see Makefile). CPU-bound steps
# (08, 09, 10, 06, 12, 13, 14) were killed by the login node's ~1GB memcg limit when
# run directly there — must go through Slurm. Script 11 needs the GPU, so the whole
# sequence runs on one gpu-partition allocation rather than splitting jobs.
#
# Everything lives under Kelly's PI project space, never $HOME. See
# reports/bouchet_login_howto.md §0.

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876

module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"

cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

echo "=== Node: $(hostname) ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

run_step () {
    local label="$1"; shift
    echo ""
    echo "=== STEP: $label ($(date -u +%Y-%m-%dT%H:%M:%SZ)) ==="
    "$@"
    echo "=== STEP DONE: $label ($(date -u +%Y-%m-%dT%H:%M:%SZ)) ==="
}

run_step "08 candidate generation" uv run python scripts/08_match_candidates.py
run_step "09 rule-based verification" uv run python scripts/09_llm_verify_matches.py
run_step "10 dedup into events" uv run python scripts/10_dedup_into_events.py
run_step "06 body-fetch (verified-only)" uv run python scripts/06_fetch_article_bodies.py --verified-only
run_step "11 analysis embeddings (GPU)" uv run python scripts/11_embed_for_analysis.py
run_step "12 assemble dataset" uv run python scripts/12_assemble_dataset.py
run_step "13 purge + compute shocks" uv run python scripts/13_purge_and_compute_shocks.py
run_step "14 feasibility gate" uv run python scripts/14_feasibility_gate.py

echo ""
echo "=== PIPELINE COMPLETE ==="
ls -la data/analysis/_FOCAL_SUCCESS
