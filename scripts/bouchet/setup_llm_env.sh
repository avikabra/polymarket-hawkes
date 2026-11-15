#!/bin/bash
# One-time: create thesis-ingest/.venv-llm with vLLM. Leaves thesis-polymarket/.venv alone.
# Usage (login node): bash scripts/bouchet/setup_llm_env.sh

set -euo pipefail

PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"

cd "$PROJECT_ROOT/thesis-ingest"
uv venv --no-config --clear --python 3.12 .venv-llm
uv pip install --no-config --python .venv-llm/bin/python "vllm>=0.17" pyarrow pandas pyyaml
.venv-llm/bin/python -c "import vllm; print('vllm', vllm.__version__)"
