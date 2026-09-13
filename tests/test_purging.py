"""Tests for src/analysis/purging.py."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.purging import _CAT_ORDER, _one_hot_category, purge_by_category

_RNG = np.random.default_rng(42)
_N = 60   # number of training articles
_D = 16   # embedding dimension
_N_FEATURES = 4 + len(_CAT_ORDER)  # price + time + volume + prior_count + category one-hots


def _make_data(n: int = _N, d: int = _D, split: str = "train", category: str = "price_ladder") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create synthetic (tuples_df, embeddings_df) with known linear structure."""
    X = _RNG.standard_normal((n, _N_FEATURES)).astype(np.float32)

    # True coefficient matrix B ∈ R^{d×5}; we'll use first 5 features
    B_true = _RNG.standard_normal((5, d)).astype(np.float32) * 0.5
    noise = _RNG.standard_normal((n, d)).astype(np.float32) * 0.1
    E = X[:, :5] @ B_true + noise

    base_ts = 1_720_000_000
    tuples_rows = []
    for i in range(n):
        tuples_rows.append({
            "article_id": f"a{i}",
            "market_id": f"m{i}",
            "category": category,
            "price_at_article": float(X[i, 0]),
            "time_to_resolution_days": float(X[i, 1]),
            "volume_24h_usdc": float(X[i, 2]),
            "prior_article_count": int(abs(X[i, 3]) * 10),
            "market_resolved_at": None,
        })
    tuples_df = pd.DataFrame(tuples_rows)

    emb_rows = [{"article_id": f"a{i}", "analysis_embedding": E[i]} for i in range(n)]
    emb_df = pd.DataFrame(emb_rows)

    return tuples_df, emb_df


def test_purging_returns_one_row_per_article():
    tuples_df, emb_df = _make_data(n=_N)
    result = purge_by_category(
        tuples_df=tuples_df,
        embeddings_df=emb_df,
        train_before="2100-01-01",  # all rows go to train
        val_before="2200-01-01",
        lambda_grid=[1.0, 10.0],
        cv_folds=3,
    )
    assert len(result) == _N
    assert "article_id" in result.columns
    assert "market_id" in result.columns
    assert "shock_embedding" in result.columns
    assert "raw_embedding" in result.columns
    assert "lambda_chosen" in result.columns


def test_purging_raw_embedding_has_correct_dim():
    tuples_df, emb_df = _make_data(n=_N)
    result = purge_by_category(
        tuples_df=tuples_df,
        embeddings_df=emb_df,
        train_before="2100-01-01",
        val_before="2200-01-01",
        lambda_grid=[1.0],
        cv_folds=3,
    )
    first_raw = result["raw_embedding"].iloc[0]
    assert len(first_raw) == _D


def test_purging_market_id_preserved():
    tuples_df, emb_df = _make_data(n=_N)
    result = purge_by_category(
        tuples_df=tuples_df,
        embeddings_df=emb_df,
        train_before="2100-01-01",
        val_before="2200-01-01",
        lambda_grid=[1.0],
        cv_folds=3,
    )
    # All market_ids should be non-null strings matching the original tuples
    assert result["market_id"].notna().all()
    expected_mids = set(tuples_df["market_id"].astype(str).tolist())
    assert set(result["market_id"].astype(str).tolist()).issubset(expected_mids)


def test_purging_shock_has_correct_dim():
    tuples_df, emb_df = _make_data(n=_N)
    result = purge_by_category(
        tuples_df=tuples_df,
        embeddings_df=emb_df,
        train_before="2100-01-01",
        val_before="2200-01-01",
        lambda_grid=[1.0],
        cv_folds=3,
    )
    first_shock = result["shock_embedding"].iloc[0]
    assert len(first_shock) == _D


def test_purging_reduces_r2_on_synthetic_signal():
    """Verify residuals are less predictable than raw embeddings (rough sanity check)."""
    tuples_df, emb_df = _make_data(n=_N)
    result = purge_by_category(
        tuples_df=tuples_df,
        embeddings_df=emb_df,
        train_before="2100-01-01",
        val_before="2200-01-01",
        lambda_grid=[1.0, 10.0, 100.0],
        cv_folds=3,
    )
    # Residual norm should be smaller than raw embedding norm (signal removed)
    raw_norms = np.stack(emb_df["analysis_embedding"].tolist())
    shock_norms = np.stack(result["shock_embedding"].tolist())
    assert shock_norms.var(axis=0).mean() < raw_norms.var(axis=0).mean()


def test_purging_oos_residuals_are_computed():
    """OOS split articles should have their residuals from a model trained on train split."""
    n_train = 40
    n_oos = 10
    # Mark last n_oos as val split by giving them a later resolved_at
    tuples_train, emb_train = _make_data(n=n_train)
    tuples_oos, emb_oos = _make_data(n=n_oos)
    # Set market ids different to avoid overlap; adjust article ids
    tuples_oos["article_id"] = [f"oos_{i}" for i in range(n_oos)]
    tuples_oos["market_resolved_at"] = pd.Timestamp("2025-06-01", tz="UTC")
    emb_oos["article_id"] = tuples_oos["article_id"].tolist()

    tuples_df = pd.concat([tuples_train, tuples_oos], ignore_index=True)
    emb_df = pd.concat([emb_train, emb_oos], ignore_index=True)

    result = purge_by_category(
        tuples_df=tuples_df,
        embeddings_df=emb_df,
        train_before="2025-01-01",
        val_before="2026-01-01",
        lambda_grid=[1.0],
        cv_folds=3,
    )
    oos_result = result[result["article_id"].isin(tuples_oos["article_id"].tolist())]
    assert len(oos_result) == n_oos
    assert (oos_result["split"] == "val").all()


def test_one_hot_produces_expected_contract_family_columns():
    """One-hot column set must match the real contract_family values, not the old sports set."""
    df = pd.DataFrame({"category": ["price_ladder", "corporate_event", "valuation_ladder"]})
    out = _one_hot_category(df.copy())

    expected_cols = {f"cat_{c}" for c in _CAT_ORDER}
    actual_cat_cols = {c for c in out.columns if c.startswith("cat_")}
    assert actual_cat_cols == expected_cols

    # Sanity: old sports columns must be gone, and the set is the schema's contract_family values.
    assert "cat_nfl" not in out.columns
    assert set(_CAT_ORDER) == {
        "price_ladder",
        "market_cap_ladder",
        "valuation_ladder",
        "revenue_ladder",
        "other_ladder",
        "corporate_event",
        "other",
    }

    # Rows one-hot correctly against the fixed order.
    assert out.loc[0, "cat_price_ladder"] == 1.0
    assert out.loc[0, "cat_corporate_event"] == 0.0
    assert out.loc[1, "cat_corporate_event"] == 1.0
    assert out.loc[2, "cat_valuation_ladder"] == 1.0


def test_one_hot_unknown_category_raises():
    """An unseen category must fail loudly, not silently produce an all-zero (inert) row —
    a silent all-zero one-hot is exactly the bug being fixed here (stale sports categories
    against contract_family data)."""
    df = pd.DataFrame({"category": ["price_ladder", "nfl"]})
    with pytest.raises(ValueError, match="nfl"):
        _one_hot_category(df.copy())


def test_one_hot_column_order_and_width_stable_across_category_subsets():
    """The one-hot column set/order must not depend on which categories are present in the
    input — required so train/val/test splits (which may see different category subsets)
    always produce the same feature width/order for the ridge regression."""
    df_full = pd.DataFrame({"category": list(_CAT_ORDER)})
    df_subset = pd.DataFrame({"category": ["price_ladder"]})

    out_full = _one_hot_category(df_full.copy())
    out_subset = _one_hot_category(df_subset.copy())

    full_cat_cols = [c for c in out_full.columns if c.startswith("cat_")]
    subset_cat_cols = [c for c in out_subset.columns if c.startswith("cat_")]
    assert full_cat_cols == subset_cat_cols
    assert len(full_cat_cols) == len(_CAT_ORDER)
