#!/bin/bash
#SBATCH --job-name=diag-conflation
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_diag_conflation_%j.out
#SBATCH --error=logs/bouchet_diag_conflation_%j.err

set -euo pipefail
PROJECT_ROOT=/nfs/roberts/project/pi_btk22/ak2876
module load miniconda
export PATH="$PROJECT_ROOT/.local/bin:$PATH"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
cd "$PROJECT_ROOT/thesis-polymarket"
mkdir -p logs

uv run python -c "
import pandas as pd
import hashlib
from pathlib import Path
import sqlite3

BODIES_DIR = Path('data/news/bodies')

# Load the full training-relevant article universe with market_id + category
tuples = pd.read_parquet('data/analysis/tuples.parquet', columns=['article_id','market_id','group_id','category','canonical_ts'])
print('total tuples rows (article x market):', len(tuples))
print('distinct article_ids:', tuples['article_id'].nunique())

# Hash body text for every distinct article_id with a real body file
article_ids = tuples['article_id'].unique().tolist()
hashes = {}
lengths = {}
missing = 0
for aid in article_ids:
    p = BODIES_DIR / f'{aid}.txt'
    if not p.exists():
        missing += 1
        continue
    text = p.read_text(encoding='utf-8').strip()
    if not text:
        continue
    norm = ' '.join(text.split())  # normalize whitespace
    h = hashlib.sha256(norm.encode()).hexdigest()
    hashes[aid] = h
    lengths[aid] = len(norm)

print()
print('articles with real body text:', len(hashes))

hash_df = pd.DataFrame({'article_id': list(hashes.keys()), 'body_hash': list(hashes.values())})
dup_counts = hash_df.groupby('body_hash')['article_id'].nunique()
dup_hashes = dup_counts[dup_counts > 1]
print('distinct body-text hashes:', hash_df['body_hash'].nunique())
print('hashes shared by >1 article_id (exact duplicate content):', len(dup_hashes))
print('total article_ids involved in an exact-duplicate cluster:', dup_hashes.sum())
print(f'  = {100*dup_hashes.sum()/len(hashes):.1f}% of all full-text articles')
print()

# For duplicate clusters, check: same market or different markets?
hash_to_aids = hash_df.groupby('body_hash')['article_id'].apply(list).to_dict()
same_market_dup_rows = 0
cross_market_dup_articles = 0
for h, aids in hash_to_aids.items():
    if len(aids) < 2:
        continue
    sub = tuples[tuples['article_id'].isin(aids)]
    markets_touched = sub['market_id'].nunique()
    # same-market pseudo-replication: >1 distinct article_id with identical text
    # matched to the SAME market (inflates that market's article count with
    # zero real information diversity)
    per_market_counts = sub.groupby('market_id')['article_id'].nunique()
    same_market_dup_rows += (per_market_counts[per_market_counts > 1] - 1).sum()
    if markets_touched > 1:
        cross_market_dup_articles += len(aids)

print('rows of same-market pseudo-replication (identical body text, same market, counted as separate articles):', same_market_dup_rows)
print('articles whose duplicate content spans multiple DIFFERENT markets (legitimate fan-out, not conflation):', cross_market_dup_articles)
print()

# Per-category duplication rate
tuples_with_hash = tuples.merge(hash_df, on='article_id', how='inner')
print('=== per-category duplication rate (of full-text articles) ===')
for cat, g in tuples_with_hash.groupby('category'):
    g_unique_aids = g.drop_duplicates(subset='article_id')
    n = len(g_unique_aids)
    dup_n = g_unique_aids['body_hash'].isin(dup_hashes.index).sum()
    print(f'{cat:20s} n_full_text={n:6d}  in_dup_cluster={dup_n:6d} ({100*dup_n/max(n,1):.1f}%)')

# Show a few example duplicate clusters for manual sanity check
print()
print('=== sample duplicate clusters (top 5 by size) ===')
top_dup = dup_counts.sort_values(ascending=False).head(5)
for h, cnt in top_dup.items():
    aids = hash_to_aids[h]
    sub = tuples[tuples['article_id'].isin(aids)]
    print(f'hash={h[:12]}... n_articles={cnt}  markets={sub[\"market_id\"].nunique()}  categories={sub[\"category\"].unique().tolist()}  len={lengths[aids[0]]}')
"
