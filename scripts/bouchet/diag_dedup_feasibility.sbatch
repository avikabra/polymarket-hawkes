#!/bin/bash
#SBATCH --job-name=diag-dedupfeas
#SBATCH --partition=devel
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --account=pi_btk22
#SBATCH --output=logs/bouchet_diag_dedupfeas_%j.out
#SBATCH --error=logs/bouchet_diag_dedupfeas_%j.err

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

BODIES_DIR = Path('data/news/bodies')

tuples = pd.read_parquet('data/analysis/tuples.parquet', columns=['article_id','market_id','category'])
shock = pd.read_parquet('data/analysis/shock_embeddings.parquet', columns=['article_id','market_id','split'])
shock = shock.drop_duplicates(subset=['article_id','market_id'])
tuples = tuples.merge(shock, on=['article_id','market_id'], how='left')

article_ids = tuples['article_id'].unique().tolist()
hashes = {}
for aid in article_ids:
    p = BODIES_DIR / f'{aid}.txt'
    if not p.exists():
        continue
    text = p.read_text(encoding='utf-8').strip()
    if not text:
        continue
    norm = ' '.join(text.split())
    hashes[aid] = hashlib.sha256(norm.encode()).hexdigest()

tuples['body_hash'] = tuples['article_id'].map(hashes)
tuples['content_key'] = tuples['body_hash'].fillna(tuples['article_id'])

print('=== Feasibility-relevant metrics: RAW (current, article_id-counted) vs DEDUPED (distinct body content per market) ===')
print()
for cat, g in tuples.groupby('category'):
    raw_art_per_market = g.groupby('market_id')['article_id'].nunique()
    dedup_art_per_market = g.groupby('market_id')['content_key'].nunique()
    n_markets = g['market_id'].nunique()
    raw_med = raw_art_per_market.median()
    dedup_med = dedup_art_per_market.median()
    pct_inflation = 100 * (raw_med - dedup_med) / raw_med if raw_med else 0
    print(f'{cat:20s} n_markets={n_markets:5d}  Med.Art RAW={raw_med:.1f}  Med.Art DEDUPED={dedup_med:.1f}  inflation={pct_inflation:.1f}%')

print()
print('=== TRAIN split only: distinct articles vs distinct content ===')
for cat, g in tuples[tuples['split']=='train'].groupby('category'):
    raw_n = g['article_id'].nunique()
    dedup_n = g['content_key'].nunique()
    print(f'{cat:20s} train raw distinct articles={raw_n:6d}  train distinct CONTENT={dedup_n:6d}  reduction={100*(raw_n-dedup_n)/max(raw_n,1):.1f}%')
"
