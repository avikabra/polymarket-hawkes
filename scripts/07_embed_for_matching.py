"""Script 07: Embed news corpus (title+lede) and market universe with BGE-large; build FAISS index.

This is the MATCHING embedding pass. It uses BAAI/bge-large-en-v1.5 (float16, 1024-dim)
on title+lede only. Do not confuse with the analysis embedding pass (script 11).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faiss
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.matching.embedder import BGEEmbedder, DEFAULT_MODEL
from src.matching.faiss_index import build_index, save_index
from src.news.normalizer import load_feed_articles, load_gdelt_articles, normalize_and_deduplicate
from src.utils import get_logger

EMBEDDINGS_DIR = Path("data/news/matching_embeddings")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")

ARTICLE_EMB_PATH = EMBEDDINGS_DIR / "article_embeddings.parquet"
MARKET_EMB_PATH = EMBEDDINGS_DIR / "market_embeddings.parquet"
FAISS_INDEX_PATH = EMBEDDINGS_DIR / "articles.faiss"
ARTICLE_ID_IDX_PATH = EMBEDDINGS_DIR / "article_id_index.parquet"

log = get_logger(__name__)


def _load_corpus() -> pd.DataFrame:
    gdelt_df = load_gdelt_articles(str(GDELT_DIR)) if GDELT_DIR.exists() else pd.DataFrame()
    feed_df = load_feed_articles(str(FEEDS_DIR)) if FEEDS_DIR.exists() else pd.DataFrame()
    if gdelt_df.empty and feed_df.empty:
        return pd.DataFrame()
    return normalize_and_deduplicate(gdelt_df, feed_df)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch-size", type=int, default=128,
        help="Encoding batch size. Use 512+ on Colab/GPU; keep ≤128 on 8 GB Apple Silicon."
    )
    args = parser.parse_args()

    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    # Load corpus and markets BEFORE loading the model so that the pandas DataFrames
    # don't compete with MPS/CUDA model buffers on unified / limited memory.
    articles_df = _load_corpus()
    log.info("corpus loaded", rows=len(articles_df))
    universe_df = pd.read_parquet(UNIVERSE_PATH)
    log.info("universe loaded", markets=len(universe_df))

    embedder = BGEEmbedder(DEFAULT_MODEL, batch_size=args.batch_size)

    # --- Articles (title + lede only — matching embeddings) ---
    article_emb_df = embedder.embed_articles(
        articles_df, existing_parquet_path=str(ARTICLE_EMB_PATH)
    )
    del articles_df  # free ~500MB before writing
    if not article_emb_df.empty:
        pq.write_table(pa.Table.from_pandas(article_emb_df), ARTICLE_EMB_PATH)

    # --- Markets (question + description) ---
    market_emb_df = embedder.embed_markets(universe_df)
    del universe_df
    pq.write_table(pa.Table.from_pandas(market_emb_df), MARKET_EMB_PATH)

    # --- FAISS index ---
    if not article_emb_df.empty:
        vecs = np.stack([
            np.frombuffer(b, dtype=np.float16) for b in article_emb_df["embedding"]
        ])
        index = build_index(vecs)
        id_df = pd.DataFrame({
            "faiss_row": np.arange(len(article_emb_df), dtype=np.int64),
            "article_id": article_emb_df["article_id"].tolist(),
        })
    else:
        index = faiss.IndexFlatIP(1024)
        id_df = pd.DataFrame({
            "faiss_row": pd.Series(dtype="int64"),
            "article_id": pd.Series(dtype="str"),
        })

    save_index(index, str(FAISS_INDEX_PATH))
    pq.write_table(pa.Table.from_pandas(id_df), ARTICLE_ID_IDX_PATH)

    (EMBEDDINGS_DIR / "_SUCCESS").touch()

    print(f"Articles embedded: {len(article_emb_df)}")
    print(f"Markets embedded:  {len(market_emb_df)}")
    if not article_emb_df.empty:
        print(f"Embedding matrix shape: {vecs.shape}")
    print(f"FAISS index total vectors: {index.ntotal}")


if __name__ == "__main__":
    main()
