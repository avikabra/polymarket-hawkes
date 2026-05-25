"""Script 06: Embed news corpus and market universe, build FAISS index."""

from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.matching.embedder import BGEEmbedder, DEFAULT_MODEL
from src.matching.faiss_index import build_index, save_index
from src.news.normalizer import load_feed_articles, load_gdelt_articles, normalize_and_deduplicate
from src.utils import get_logger

EMBEDDINGS_DIR = Path("data/news/embeddings")
UNIFIED_DIR = Path("data/news/unified")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")
UNIVERSE_PATH = Path("data/polymarket/universe.parquet")

ARTICLE_EMB_PATH = EMBEDDINGS_DIR / "article_embeddings.parquet"
MARKET_EMB_PATH = EMBEDDINGS_DIR / "market_embeddings.parquet"
FAISS_INDEX_PATH = EMBEDDINGS_DIR / "articles.faiss"
ARTICLE_ID_IDX_PATH = EMBEDDINGS_DIR / "article_id_index.parquet"

log = get_logger(__name__)


def _load_corpus() -> pd.DataFrame:
    if UNIFIED_DIR.exists() and any(UNIFIED_DIR.rglob("*.parquet")):
        paths = list(UNIFIED_DIR.rglob("*.parquet"))
        return pa.concat_tables([pq.read_table(p) for p in paths]).to_pandas()
    gdelt_df = load_gdelt_articles(str(GDELT_DIR)) if GDELT_DIR.exists() else pd.DataFrame()
    feed_df = load_feed_articles(str(FEEDS_DIR)) if FEEDS_DIR.exists() else pd.DataFrame()
    if gdelt_df.empty and feed_df.empty:
        return pd.DataFrame()
    return normalize_and_deduplicate(gdelt_df, feed_df)


def main() -> None:
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    embedder = BGEEmbedder(DEFAULT_MODEL)

    # --- Articles ---
    articles_df = _load_corpus()
    log.info("corpus loaded", rows=len(articles_df))
    article_emb_df = embedder.embed_articles(
        articles_df, existing_parquet_path=str(ARTICLE_EMB_PATH)
    )
    if not article_emb_df.empty:
        pq.write_table(pa.Table.from_pandas(article_emb_df), ARTICLE_EMB_PATH)

    # --- Markets ---
    universe_df = pd.read_parquet(UNIVERSE_PATH)
    market_emb_df = embedder.embed_markets(universe_df)
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
