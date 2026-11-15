import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.matching.embedder import BGEEmbedder, DEFAULT_MODEL, EMBED_DIM, _build_group_text
from src.matching.faiss_index import build_index, search


def test_build_group_text_corporate_event_uses_member_question():
    row = {
        "group_id": "0xabc",
        "contract_family": "corporate_event",
        "company_name": "Boeing",
        "ticker": None,
        "ladder_metric": None,
        "price_expiry_month": None,
        "member_market_ids": ["0xabc"],
        "strikes": [],
    }
    universe_lookup = {
        "0xabc": {
            "market_id": "0xabc",
            "question": "Will Boeing announce a new CEO in 2025?",
            "description": "Resolves YES if Boeing names a new chief executive.",
        }
    }
    text = _build_group_text(row, universe_lookup)
    assert text == (
        "Will Boeing announce a new CEO in 2025? "
        "Resolves YES if Boeing names a new chief executive."
    )


def test_build_group_text_corporate_event_missing_member_returns_empty():
    row = {
        "contract_family": "corporate_event",
        "member_market_ids": ["0xmissing"],
    }
    text = _build_group_text(row, universe_lookup={})
    assert text == ""


def test_build_group_text_ladder_uses_group_columns_not_member_questions():
    row = {
        "group_id": "gamestop_market_cap_2024-06",
        "contract_family": "market_cap_ladder",
        "company_name": "GameStop",
        "ticker": "GME",
        "ladder_metric": "market_cap",
        "price_expiry_month": "2024-06",
        "member_market_ids": ["0x1", "0x2"],
        "strikes": np.array([16.0, 6.0]),
    }
    text = _build_group_text(row, universe_lookup={})
    assert text == "GameStop (GME) market_cap forecast for 2024-06: strikes [6.0, 16.0]"
    # Member questions must not appear — group columns only.
    assert "0x1" not in text and "0x2" not in text


def test_build_group_text_ladder_private_company_no_ticker():
    row = {
        "contract_family": "valuation_ladder",
        "company_name": "Databricks",
        "ticker": None,
        "ladder_metric": "valuation",
        "price_expiry_month": "2025-01",
        "member_market_ids": ["0x1"],
        "strikes": [50e9],
    }
    text = _build_group_text(row, universe_lookup={})
    assert "(private)" in text
    assert "Databricks" in text


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
    result, done = embedder.embed_articles(articles_df, existing_parquet_path=existing_path)

    assert done is True
    assert len(result) == 2
    existing_row = result[result["article_id"] == existing_id].iloc[0]
    stored_emb = np.frombuffer(existing_row["embedding"], dtype=np.float16)
    assert np.allclose(stored_emb, 0.0)
