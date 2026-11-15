#!/bin/bash
#SBATCH --job-name=diag-textqual
#SBATCH --partition=devel
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_diag_textqual_%j.out
#SBATCH --error=logs/bouchet_diag_textqual_%j.err

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

print('=== Overall (all verified/matched articles feeding tuples.parquet) ===')
print('n distinct article_id in tuples.parquet:', len(tuples))
merged = tuples.merge(emb, on='article_id', how='left')
merged['embedding_source'] = merged['embedding_source'].fillna('NO_EMBEDDING_FOUND')
print(merged['embedding_source'].value_counts())
print()

print('=== Per-category body-text completeness (tuples.parquet universe) ===')
for cat, g in merged.groupby('category'):
    n = len(g)
    full = (g['embedding_source']=='full_text').sum()
    print(f'{cat:20s} n={n:6d}  full_text={full:6d} ({100*full/n:.1f}%)  headline_only={n-full:6d} ({100*(n-full)/n:.1f}%)')
print()

print('=== TRAINING SET ONLY (shock_embeddings.parquet, split=train, valid_24h=True) ===')
train = shock[(shock['split']=='train') & (shock['valid_24h']==True)]
train_merged = train.merge(emb, on='article_id', how='left')
train_merged['embedding_source'] = train_merged['embedding_source'].fillna('NO_EMBEDDING_FOUND')
print('n train rows (valid_24h):', len(train_merged))
print(train_merged['embedding_source'].value_counts())
print()
print('per-category, TRAIN split only:')
for cat, g in train_merged.groupby('category'):
    n = len(g)
    full = (g['embedding_source']=='full_text').sum()
    print(f'{cat:20s} n={n:6d}  full_text={full:6d} ({100*full/n:.1f}%)  headline_only={n-full:6d} ({100*(n-full)/n:.1f}%)')
print()

print('=== ALL SPLITS combined (train+val+test), valid_24h=True ===')
allv = shock[shock['valid_24h']==True]
allv_merged = allv.merge(emb, on='article_id', how='left')
allv_merged['embedding_source'] = allv_merged['embedding_source'].fillna('NO_EMBEDDING_FOUND')
print('n rows:', len(allv_merged))
print(allv_merged['embedding_source'].value_counts())
for cat, g in allv_merged.groupby('category'):
    n = len(g)
    full = (g['embedding_source']=='full_text').sum()
    print(f'{cat:20s} n={n:6d}  full_text={full:6d} ({100*full/n:.1f}%)')

# Save the list of article_ids missing full text (for potential re-fetch)
missing = merged[merged['embedding_source'] != 'full_text']['article_id'].unique()
pd.Series(missing).to_csv('/tmp/missing_body_article_ids.csv', index=False, header=['article_id'])
print()
print('Total distinct articles missing full body text (tuples.parquet universe):', len(missing))
"
