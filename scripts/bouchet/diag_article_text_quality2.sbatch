#!/bin/bash
#SBATCH --job-name=diag-textqual2
#SBATCH --partition=devel
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_diag_textqual2_%j.out
#SBATCH --error=logs/bouchet_diag_textqual2_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

uv run python -c "
import pandas as pd

tuples = pd.read_parquet('data/analysis/tuples.parquet', columns=['article_id','category'])
tuples = tuples.drop_duplicates(subset=['article_id'])
shock = pd.read_parquet('data/analysis/shock_embeddings.parquet', columns=['article_id','category','split','valid_24h'])
emb = pd.read_parquet('data/news/analysis_embeddings/analysis_embeddings.parquet', columns=['article_id','embedding_source'])

print('=== Overall (all verified/matched articles) ===')
merged = tuples.merge(emb, on='article_id', how='left')
merged['embedding_source'] = merged['embedding_source'].fillna('NO_EMBEDDING_FOUND')
print(merged['embedding_source'].value_counts())
print()

print('=== Per-category (tuples.parquet universe) ===')
for cat, g in merged.groupby('category'):
    n = len(g)
    full = (g['embedding_source']=='full_text').sum()
    print(f'{cat:20s} n={n:6d}  full_text={full:6d} ({100*full/n:.1f}%)')
print()

print('=== TRAIN split (shock_embeddings, valid_24h=True) ===')
train = shock[(shock['split']=='train') & (shock['valid_24h']==True)]
train_merged = train.merge(emb, on='article_id', how='left')
train_merged['embedding_source'] = train_merged['embedding_source'].fillna('NO_EMBEDDING_FOUND')
print('n train rows:', len(train_merged))
print(train_merged['embedding_source'].value_counts())
print()
for cat, g in train_merged.groupby('category'):
    n = len(g)
    full = (g['embedding_source']=='full_text').sum()
    print(f'{cat:20s} n={n:6d}  full_text={full:6d} ({100*full/n:.1f}%)')
"
