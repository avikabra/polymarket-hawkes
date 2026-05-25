import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.matching.embedder import BGEEmbedder, DEFAULT_MODEL, EMBED_DIM
from src.matching.faiss_index import build_index, search


@pytest.fixture(scope="module")
def embedder():
    return BGEEmbedder(DEFAULT_MODEL)


def test_embed_texts_shape(embedder):
    vecs = embedder.embed_texts(["Hello world", "Test sentence", "Another one"])
    assert vecs.shape == (3, EMBED_DIM)


def test_embed_texts_dtype(embedder):
    vecs = embedder.embed_texts(["Hello world"])
    assert vecs.dtype == np.float16


def test_build_index_nearest_neighbor(embedder):
    texts = ["Basketball game tonight", "Python programming language", "Stock market crash"]
    vecs = embedder.embed_texts(texts)
    index = build_index(vecs)
    scores, indices = search(index, vecs[0:1], k=1)
    assert indices[0][0] == 0


def test_embed_articles_skips_existing(embedder, tmp_path):
    existing_id = "abc123"
    existing_emb = np.zeros(EMBED_DIM, dtype=np.float16)
    existing_df = pd.DataFrame([{"article_id": existing_id, "embedding": existing_emb.tobytes()}])
    existing_path = str(tmp_path / "article_embeddings.parquet")
    pq.write_table(pa.Table.from_pandas(existing_df), existing_path)

    articles_df = pd.DataFrame([
        {"article_id": existing_id, "title": "Old article", "lede": None},
        {"article_id": "new456", "title": "New article", "lede": "Some lede text"},
    ])
    result = embedder.embed_articles(articles_df, existing_parquet_path=existing_path)

    assert len(result) == 2
    existing_row = result[result["article_id"] == existing_id].iloc[0]
    stored_emb = np.frombuffer(existing_row["embedding"], dtype=np.float16)
    assert np.allclose(stored_emb, 0.0)
