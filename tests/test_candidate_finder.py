import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.matching.candidate_finder import CandidateFinder
from src.matching.faiss_index import build_index, save_index

_DIM = 1024
_BASE = datetime(2024, 3, 15, tzinfo=timezone.utc)
_WINDOW_START = _BASE - timedelta(hours=1)
_WINDOW_END = _BASE + timedelta(days=2)


@pytest.fixture
def tiny_setup(tmp_path):
    rng = np.random.default_rng(42)
    vecs = rng.random((5, _DIM)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)

    faiss_path = str(tmp_path / "articles.faiss")
    save_index(build_index(vecs), faiss_path)

    id_df = pd.DataFrame({
        "faiss_row": np.arange(5, dtype=np.int64),
        "article_id": [f"article_{i}" for i in range(5)],
    })
    id_path = str(tmp_path / "article_id_index.parquet")
    pq.write_table(pa.Table.from_pandas(id_df), id_path)

    meta_rows = [
        {"article_id": "article_0", "published_at": _BASE,               "timestamp_precision": "minute", "raw_metadata_json": None},
        {"article_id": "article_1", "published_at": _BASE + timedelta(days=1), "timestamp_precision": "minute", "raw_metadata_json": None},
        {"article_id": "article_2", "published_at": _BASE - timedelta(days=10), "timestamp_precision": "minute", "raw_metadata_json": None},
        {"article_id": "article_3", "published_at": None,                "timestamp_precision": "day",    "raw_metadata_json": json.dumps({"date_int": 20240315000000})},
        {"article_id": "article_4", "published_at": None,                "timestamp_precision": "day",    "raw_metadata_json": json.dumps({"date_int": 20230101000000})},
    ]
    meta_path = str(tmp_path / "meta.parquet")
    pq.write_table(pa.Table.from_pandas(pd.DataFrame(meta_rows)), meta_path)

    return {"faiss_path": faiss_path, "id_path": id_path, "meta_path": meta_path, "vecs": vecs}


def test_find_candidates_max_k(tiny_setup):
    finder = CandidateFinder(tiny_setup["faiss_path"], tiny_setup["id_path"], tiny_setup["meta_path"], k=2)
    results = finder.find_candidates("mkt1", tiny_setup["vecs"][0], _WINDOW_START, _WINDOW_END)
    assert len(results) <= 2


def test_time_window_filter(tiny_setup):
    finder = CandidateFinder(tiny_setup["faiss_path"], tiny_setup["id_path"], tiny_setup["meta_path"], k=150)
    results = finder.find_candidates("mkt1", tiny_setup["vecs"][0], _WINDOW_START, _WINDOW_END)
    ids = {r["article_id"] for r in results}
    assert "article_2" not in ids  # pub_at 10 days before window
    assert "article_4" not in ids  # GDELT date 2023-01-01, outside window


def test_result_dict_keys(tiny_setup):
    finder = CandidateFinder(tiny_setup["faiss_path"], tiny_setup["id_path"], tiny_setup["meta_path"], k=150)
    results = finder.find_candidates("mkt1", tiny_setup["vecs"][0], _WINDOW_START, _WINDOW_END)
    assert results
    required = {"market_id", "article_id", "embedding_score", "article_published_at", "timestamp_precision"}
    for r in results:
        assert set(r.keys()) == required
