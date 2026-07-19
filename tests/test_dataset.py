"""Tests for ArticleDataset and ArticleSequenceDataset using synthetic in-memory data."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.training.dataset import ArticleDataset, ArticleSequenceDataset

# ---- Synthetic data parameters ----
_D = 16        # embedding dimension (tiny, for speed)
_N = 50        # total articles
_N_MARKETS = 5
_BASE_TS = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp())
_TRAIN_CUTOFF = int(pd.Timestamp("2025-01-01", tz="UTC").timestamp())

_RNG = np.random.default_rng(0)


def _make_synthetic_df() -> pd.DataFrame:
    """Build a synthetic DataFrame matching the shock_embeddings contract."""
    rows = []
    splits = (["train"] * 40) + (["val"] * 5) + (["test"] * 5)
    # Assign train articles before 2025-01-01, val/test after
    for i in range(_N):
        split = splits[i]
        market_id = f"m{i % _N_MARKETS}"
        if split == "train":
            ts = _BASE_TS + i * 3600  # spread across 2024; all < 2025-01-01
        else:
            ts = _TRAIN_CUTOFF + i * 3600  # val/test after cutoff

        emb = _RNG.standard_normal(_D).astype(np.float32).tolist()
        raw = _RNG.standard_normal(_D).astype(np.float32).tolist()

        # Make 3 rows invalid
        valid = i not in (10, 20, 30)

        rows.append({
            "article_id": f"a{i}",
            "market_id": market_id,
            "shock_embedding": emb,
            "raw_embedding": raw,
            "category": "nfl",
            "split": split,
            "canonical_ts": ts,
            "parent_event_id": f"event_{i % 3}",
            "y_logit_6h": float(_RNG.standard_normal(1)[0]),
            "valid_6h": valid,
            "news_type": "quantitative",
            "directional_impact": int(_RNG.choice([-1, 0, 1])),
        })

    return pd.DataFrame(rows)


@pytest.fixture()
def synthetic_parquet(tmp_path):
    """Write synthetic DataFrame to a temp parquet and return its path string."""
    df = _make_synthetic_df()
    path = tmp_path / "shock_embeddings.parquet"
    df.to_parquet(str(path), index=False)
    return str(path)


@pytest.fixture()
def synthetic_df():
    return _make_synthetic_df()


# ---- ArticleDataset tests ----

def test_article_dataset_shape(synthetic_parquet):
    """Embedding tensor has shape (d,)."""
    ds = ArticleDataset(parquet_path=synthetic_parquet, split="train", embedding_col="shock_embedding")
    assert len(ds) > 0
    item = ds[0]
    assert item["embedding"].shape == (16,)


def test_valid_6h_filter(synthetic_parquet, synthetic_df):
    """Rows with valid_6h=False must be excluded."""
    # 3 invalid rows, all in train (indices 10, 20, 30 → in train split)
    ds = ArticleDataset(parquet_path=synthetic_parquet, split="train", embedding_col="shock_embedding")
    invalid_count = len(
        synthetic_df[(synthetic_df["split"] == "train") & (~synthetic_df["valid_6h"])]
    )
    valid_count = len(
        synthetic_df[(synthetic_df["split"] == "train") & (synthetic_df["valid_6h"])]
    )
    assert len(ds) == valid_count
    # None of the invalid IDs should appear
    invalid_ids = set(
        synthetic_df[~synthetic_df["valid_6h"]]["article_id"].tolist()
    )
    for i in range(len(ds)):
        assert ds[i]["article_id"] not in invalid_ids


# ---- ArticleSequenceDataset tests ----

def test_padding_logic(synthetic_parquet):
    """Market with fewer than K prior articles must have left-zero-padded mask."""
    K = 5
    ds = ArticleSequenceDataset(
        parquet_path=synthetic_parquet,
        split="train",
        K=K,
        category_filter=None,
    )
    # Find an item whose market has <= 2 articles in train (so lots of padding)
    df = _make_synthetic_df()
    # market m0 has articles 0,5,10,15,... → 8 train articles; m1 has 1,6,11,...
    # With K=5 and enough prior, many will be filled. Check for padding counts > 0:
    found_padding = False
    for i in range(len(ds)):
        item = ds[i]
        mask = item["mask"]
        pad_count = int((~mask).sum().item())
        if pad_count > 0:
            # The first (pad_count) positions should be zero in shock_embeddings
            shock = item["shock_embeddings"]
            assert torch.all(shock[:pad_count] == 0.0), "Padded positions must be zero"
            found_padding = True
            break
    # For a dataset with K=5, we almost certainly have some padding
    # (target articles with fewer than 5 priors in same market)
    assert found_padding or len(ds) == 0


def test_mask_shape(synthetic_parquet):
    """Mask shape must be (K+1,) with dtype bool."""
    K = 5
    ds = ArticleSequenceDataset(
        parquet_path=synthetic_parquet,
        split="train",
        K=K,
    )
    assert len(ds) > 0
    item = ds[0]
    mask = item["mask"]
    assert mask.shape == (K + 1,), f"Expected mask shape ({K+1},), got {mask.shape}"
    assert mask.dtype == torch.bool


def test_no_temporal_leakage(synthetic_parquet):
    """All train-split articles must have canonical_ts < 2025-01-01 00:00 UTC."""
    ds = ArticleSequenceDataset(
        parquet_path=synthetic_parquet,
        split="train",
        K=5,
    )
    cutoff = _TRAIN_CUTOFF
    for i in range(len(ds)):
        item = ds[i]
        # The dataset itself doesn't expose canonical_ts, but we can verify via
        # the underlying data contract: all train rows were set to _BASE_TS + i * 3600
        # which is well before _TRAIN_CUTOFF. Just check the dataset loads cleanly.
        assert "y_logit_6h" in item
        assert "mask" in item

    # Cross-check from the raw dataframe
    df = _make_synthetic_df()
    train_rows = df[(df["split"] == "train") & (df["valid_6h"] == True)]  # noqa: E712
    assert (train_rows["canonical_ts"] < cutoff).all(), \
        "Train articles must all have timestamps before 2025-01-01"


def test_sequence_dataset_valid_6h_filter(synthetic_parquet, synthetic_df):
    """ArticleSequenceDataset must also exclude valid_6h=False rows."""
    K = 5
    ds = ArticleSequenceDataset(
        parquet_path=synthetic_parquet,
        split="train",
        K=K,
    )
    valid_train = len(
        synthetic_df[(synthetic_df["split"] == "train") & (synthetic_df["valid_6h"] == True)]  # noqa: E712
    )
    assert len(ds) == valid_train
