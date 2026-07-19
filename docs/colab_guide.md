# Running the W4–6 Training Pipeline on Google Colab

This guide explains how to take the Direction 4 codebase, upload your real data, and run the full
Weeks 4–6 training + evaluation pipeline on Colab GPU.  It also shows a dry-run path using synthetic
data so you can confirm everything is wired up before burning GPU time.

---

## 1. Colab setup

### 1.1 Pick a GPU runtime

In Colab: **Runtime → Change runtime type → Hardware accelerator → T4 GPU** (or A100/L4 on Pro+).

Confirm GPU is available:
```python
import torch
print(torch.cuda.is_available())   # must be True
print(torch.cuda.get_device_name(0))
```

### 1.2 Get the code onto Colab

**Option A — clone from GitHub** (recommended if the repo is on GitHub):
```bash
!git clone https://github.com/<your-username>/thesis-polymarket.git
%cd thesis-polymarket
```

**Option B — upload a zip** (if the repo is local only):
```python
from google.colab import files
uploaded = files.upload()   # select thesis-polymarket.zip
!unzip thesis-polymarket.zip
%cd thesis-polymarket
```

### 1.3 Install dependencies

Colab pre-installs torch, numpy, pandas, scikit-learn.  Install the extras:
```bash
!pip install -q pyarrow pyyaml joblib structlog
```

Verify the package imports:
```bash
!python -c "import src"
```

---

## 2. What data to upload and where

The pipeline reads exactly one input file:

```
data/analysis/shock_embeddings.parquet
```

This file is produced by scripts 12 + 13 of the W1–3 pipeline.  It must contain the following
columns (all must be present; extra columns are ignored):

| Column | Type | Notes |
|--------|------|-------|
| `article_id` | str | Unique article identifier |
| `market_id` | str | Polymarket market slug |
| `category` | str | `"nfl"`, `"nba"`, `"politics"`, or `"geopolitics"` |
| `split` | str | `"train"`, `"val"`, or `"test"` |
| `canonical_ts` | int | Unix epoch seconds (integer, not milliseconds) |
| `valid_6h` | bool | True if market was open 6h after article publication |
| `y_logit_6h` | float | Log-odds price change over 6h window |
| `y_logit_1h` | float | Same for 1h (used in robustness checks) |
| `y_logit_24h` | float | Same for 24h |
| `shock_embedding` | list[float] | 768-dim E5-large residual (shock) |
| `raw_embedding` | list[float] | 768-dim E5-large unnormalised embedding |
| `news_type` | str | `"quantitative"`, `"qualitative"`, `"high_attention"`, `"ambiguous"` |
| `directional_impact` | int | -1, 0, or +1 |
| `parent_event_id` | str | Groups correlated markets (same real-world event) |

### Upload via Google Drive (recommended for large files)
```python
from google.colab import drive
drive.mount('/content/drive')

import shutil
shutil.copy(
    '/content/drive/MyDrive/thesis_data/shock_embeddings.parquet',
    'data/analysis/shock_embeddings.parquet'
)
```

### Upload directly
```python
import os
os.makedirs('data/analysis', exist_ok=True)
from google.colab import files
uploaded = files.upload()   # select shock_embeddings.parquet
import shutil
shutil.move('shock_embeddings.parquet', 'data/analysis/shock_embeddings.parquet')
```

---

## 3. Dry-run with synthetic data (do this first)

Before running with real data, confirm the full pipeline wiring on synthetic data (CPU, tiny epochs).
This catches import errors, path issues, and schema mismatches without touching real results.

```bash
# Generate ~600-row synthetic parquet (< 5 seconds)
!python scripts/make_synthetic_shock_embeddings.py \
    --out data/analysis/shock_embeddings.parquet \
    --n 600 --seed 42

# Validate schema and print per-split observation counts
!python scripts/15_build_sequence_dataset.py

# Run unit tests (should all pass in ~60s on CPU)
!pip install -q pytest
!python -m pytest tests/ -q

# Linear baseline (CPU, seconds)
!python scripts/16_train_linear_baseline.py --category all --embedding shock
!python scripts/16_train_linear_baseline.py --category all --embedding raw

# Quick LSTM run (2 epochs; just tests the wiring)
# Edit config/training.yaml: set lstm.max_epochs: 2 before running if you want to skip training
!python scripts/17_train_lstm.py --category all --embedding shock

# Evaluate all checkpoints found so far
!python scripts/20_evaluate_all_models.py

# Hypothesis tests
!python scripts/21_hypothesis_tests.py
```

If these all complete without errors, the pipeline is wired correctly.
Delete the synthetic data before uploading real data:
```bash
!rm data/analysis/shock_embeddings.parquet
!rm -rf models/checkpoints results/
```

---

## 4. Real training run (GPU)

Once you have `data/analysis/shock_embeddings.parquet` with real W1–3 data, run in this order.
The `--device auto` flag is the default — it picks CUDA automatically on Colab.

### 4.1 Diagnostics
```bash
!python scripts/15_build_sequence_dataset.py
```
Check output: confirm ≥100 observations per category in the test split.  If any split is near-empty,
see the spec §10 (Open Questions) about shifting the val/test cutoff.

### 4.2 Linear baseline (CPU, ~30s each)
```bash
for cat in all sports politics geopolitics; do
    for emb in shock raw; do
        python scripts/16_train_linear_baseline.py --category $cat --embedding $emb
    done
done
```

### 4.3 Hyperparameter search (optional but recommended)

Run once per architecture × category before final training.  Each search saves a JSON file that the
training scripts pick up automatically.

```python
# Example: run in a Colab cell for LSTM
import sys; sys.path.insert(0, '.')
from src.training.hparam_search import random_hparam_search
import yaml

with open('config/training.yaml') as f:
    cfg = yaml.safe_load(f)

for cat in ['sports', 'politics', 'geopolitics', 'all']:
    random_hparam_search(
        arch='lstm',
        category=cat,
        parquet_path='data/analysis/shock_embeddings.parquet',
        config=cfg.get('lstm', {}),
        n_configs=12,
        max_epochs=30,
        device='auto',
        output_path=f'models/hparam_search/lstm_{cat}_results.json',
    )
```

Repeat with `arch='tcn'` (10 configs) and `arch='transformer'` (12 configs).

### 4.4 Final training

Each script auto-detects the GPU.  Run per category and embedding:

```bash
# LSTM
for cat in all sports politics geopolitics; do
    for emb in shock raw; do
        python scripts/17_train_lstm.py --category $cat --embedding $emb
    done
done

# Transformer (most GPU-intensive; ~15-30 min per run on T4)
for cat in all sports politics geopolitics; do
    for emb in shock raw; do
        python scripts/18_train_transformer.py --category $cat --embedding $emb
    done
done

# TCN
for cat in all sports politics geopolitics; do
    for emb in shock raw; do
        python scripts/19_train_tcn.py --category $cat --embedding $emb
    done
done
```

**Resuming after a Colab disconnect:**  each script accepts `--resume` which reloads the last
saved checkpoint before continuing training.

```bash
python scripts/17_train_lstm.py --category sports --embedding shock --resume
```

### 4.5 Evaluation and hypothesis tests

```bash
# Evaluate all checkpoints → results/metrics_all.parquet + results/test_predictions.parquet
python scripts/20_evaluate_all_models.py

# Bootstrap CIs (real, clustered by parent_event_id) + H1-H4 tests
python scripts/21_hypothesis_tests.py
```

---

## 5. Checkpoint file naming

Checkpoints are saved to `models/checkpoints/` with the naming convention:

```
{arch}_{category}_{embedding}_best.pt    # neural models
linear_{category}_{embedding}.pkl        # linear baseline
```

Examples:
```
models/checkpoints/lstm_sports_shock_best.pt
models/checkpoints/transformer_all_raw_best.pt
models/checkpoints/linear_geopolitics_shock.pkl
```

Checkpoints include the training hyperparameters (`K`, architecture dims, embedding type) in the
`config` key — script 20 reads these back so eval always uses the same K as training.

---

## 6. Downloading outputs from Colab

### Download results folder
```python
import shutil
shutil.make_archive('results', 'zip', 'results')
from google.colab import files
files.download('results.zip')
```

### Download checkpoints
```python
shutil.make_archive('checkpoints', 'zip', 'models/checkpoints')
files.download('checkpoints.zip')
```

### Or copy to Drive
```python
from google.colab import drive
drive.mount('/content/drive')
shutil.copytree('results', '/content/drive/MyDrive/thesis_results/results', dirs_exist_ok=True)
shutil.copytree('models', '/content/drive/MyDrive/thesis_results/models', dirs_exist_ok=True)
```

---

## 7. Key output files

| File | Contents |
|------|----------|
| `results/metrics_all.parquet` | R²_OOS and direction accuracy per (arch, category, embedding) |
| `results/test_predictions.parquet` | Per-row test-set predictions (used for bootstrap CIs) |
| `results/bootstrap_cis.parquet` | 95% CIs clustered by parent_event_id |
| `results/hypothesis_tests.json` | H1–H4 verdicts with ΔR² and CI bounds |
| `models/checkpoints/*.pt / *.pkl` | Best-val-MSE checkpoints for all trained models |
| `models/hparam_search/*.json` | Hyperparameter search results (top-3 per arch/category) |

---

## 8. Memory tips

- **OOM on Transformer (K=20, d=768):** reduce `transformer.batch_size` in `config/training.yaml`
  from 32 to 16, or reduce `transformer.window_size` from 20 to 10.
- **Reloading after disconnect:** always run script 20 after reloading checkpoints — it re-runs
  inference on the test set and regenerates `test_predictions.parquet`.
- **Float16 embeddings:** the real parquet stores embeddings as float32 lists.  If memory is tight,
  you can post-process the parquet to float16 with:
  ```python
  import pandas as pd, numpy as np
  df = pd.read_parquet('data/analysis/shock_embeddings.parquet')
  df['shock_embedding'] = df['shock_embedding'].apply(lambda x: np.array(x, dtype=np.float16).tolist())
  df.to_parquet('data/analysis/shock_embeddings.parquet', index=False)
  ```
  Note: the models cast to float32 internally, so this only saves parquet read memory.
