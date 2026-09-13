"""Purging regression per plan §0.4.

Model:  e_i = B · x_{k,t_i} + ε_i
        where e_i ∈ R^d is the analysis embedding,
              x_{k,t_i} ∈ R^5 is the market characteristics vector,
              B is estimated by ridge regression per category.

Splits markets by resolution date (train/val/test per analysis.yaml splits).
Uses 5-fold CV within the training set to select λ.
Residuals ε̂_i = e_i - B_hat · x_i are computed out-of-sample for val and test.

Writes:
  shock_embeddings.parquet  — (article_id, market_id, shock_embedding, raw_embedding,
                               lambda_chosen, category, split)
Logs per-category R² on the training split.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

# Fixed one-hot column order for the `category` feature, which now holds
# contract_family values (project pivoted from sports to company contracts —
# see CLAUDE.md). This MUST be a hardcoded, fixed-at-import-time list — not
# derived from the data at fit time — because the same list is used to build
# the design matrix for train, val, and test; if the column set instead came
# from whatever categories happen to appear in a given split, different
# splits could produce different column widths/order and silently corrupt
# the out-of-sample residual computation. Sourced from (must be kept in sync
# with) the contract_family Literal in src/schemas/market.py:21, which is the
# closed-set source of truth.
_CAT_ORDER = [
    "price_ladder",
    "market_cap_ladder",
    "valuation_ladder",
    "revenue_ladder",
    "other_ladder",
    "corporate_event",
    "other",
]

# Characteristics columns (must all be numeric after one-hot expansion)
_CHAR_COLS = ["price_at_article", "time_to_resolution_days", "volume_24h_usdc", "prior_article_count"]


def _one_hot_category(df: pd.DataFrame) -> pd.DataFrame:
    """Add integer columns for each category.

    Raises ValueError on any category value outside _CAT_ORDER instead of
    silently emitting an all-zero row — an inert all-zero one-hot is exactly
    the bug this replaces (sports categories against contract_family data),
    so an unknown value here should fail loudly rather than repeat it.
    """
    unknown = set(df["category"].unique()) - set(_CAT_ORDER)
    if unknown:
        raise ValueError(
            f"Unknown category value(s) {sorted(unknown)} not in _CAT_ORDER {_CAT_ORDER}. "
            "Update _CAT_ORDER (kept in sync with the contract_family Literal in "
            "src/schemas/market.py) rather than silently dropping them."
        )
    for cat in _CAT_ORDER:
        df[f"cat_{cat}"] = (df["category"] == cat).astype(float)
    return df


def _build_X(df: pd.DataFrame) -> np.ndarray:
    feature_cols = _CHAR_COLS + [f"cat_{c}" for c in _CAT_ORDER]
    return df[feature_cols].to_numpy(dtype=np.float32)


def _build_E(df: pd.DataFrame) -> np.ndarray:
    """Stack shock_embedding arrays from a column of lists/arrays."""
    return np.stack(df["analysis_embedding"].tolist()).astype(np.float32)


def purge_by_category(
    tuples_df: pd.DataFrame,
    embeddings_df: pd.DataFrame,
    train_before: str,
    val_before: str,
    lambda_grid: list[float],
    cv_folds: int,
) -> pd.DataFrame:
    """Run the per-category purging regression and return shock embeddings.

    tuples_df must have columns:
      article_id, market_id, category, price_at_article, time_to_resolution_days,
      volume_24h_usdc, prior_article_count, and market_resolved_at (datetime or None).

    embeddings_df must have columns:
      article_id, analysis_embedding (numpy array or list).

    Returns DataFrame with:
      article_id, shock_embedding (list[float]), lambda_chosen, category, split.
    """
    # Merge embeddings into tuples
    merged = tuples_df.merge(embeddings_df, on="article_id", how="inner")
    merged = _one_hot_category(merged)

    # Temporal split by market resolution date
    train_cutoff = pd.Timestamp(train_before, tz="UTC")
    val_cutoff = pd.Timestamp(val_before, tz="UTC")

    def _split(resolved_at) -> str:
        if resolved_at is None:
            return "train"  # default
        ts = pd.Timestamp(resolved_at)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        if ts < train_cutoff:
            return "train"
        elif ts < val_cutoff:
            return "val"
        else:
            return "test"

    merged["split"] = merged["market_resolved_at"].apply(_split)

    result_rows = []

    for cat in merged["category"].unique():
        cat_df = merged[merged["category"] == cat].dropna(subset=_CHAR_COLS)
        if cat_df.empty:
            continue

        train_df = cat_df[cat_df["split"] == "train"]
        oos_df = cat_df[cat_df["split"].isin(["val", "test"])]

        if len(train_df) < max(cv_folds, 10):
            # Not enough data to fit — emit raw embeddings with split label
            for _, row in cat_df.iterrows():
                emb = np.array(row["analysis_embedding"], dtype=np.float32)
                result_rows.append({
                    "article_id": row["article_id"],
                    "market_id": row["market_id"],
                    "shock_embedding": emb.tolist(),
                    "raw_embedding": emb.tolist(),
                    "lambda_chosen": None,
                    "category": cat,
                    "split": row["split"],
                })
            continue

        X_train = _build_X(train_df)
        E_train = _build_E(train_df)

        # Standardize X
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)

        # Ridge with CV — fit per embedding dimension via RidgeCV
        ridge = RidgeCV(
            alphas=lambda_grid,
            cv=KFold(n_splits=cv_folds, shuffle=False),
            fit_intercept=True,
        )
        ridge.fit(X_train_s, E_train)
        lambda_chosen = float(ridge.alpha_)

        # R² on training split
        r2 = ridge.score(X_train_s, E_train)
        print(f"Category={cat} | train_n={len(train_df)} | lambda={lambda_chosen:.2g} | train_R²={r2:.4f}")

        # Compute OOS residuals (val + test)
        if not oos_df.empty:
            X_oos = scaler.transform(_build_X(oos_df))
            E_oos = _build_E(oos_df)
            E_hat_oos = ridge.predict(X_oos)
            residuals_oos = E_oos - E_hat_oos

            for i, (_, row) in enumerate(oos_df.iterrows()):
                result_rows.append({
                    "article_id": row["article_id"],
                    "market_id": row["market_id"],
                    "shock_embedding": residuals_oos[i].tolist(),
                    "raw_embedding": np.array(row["analysis_embedding"], dtype=np.float32).tolist(),
                    "lambda_chosen": lambda_chosen,
                    "category": cat,
                    "split": row["split"],
                })

        # In-sample residuals for training set (for completeness; not for architecture training)
        E_hat_train = ridge.predict(X_train_s)
        residuals_train = E_train - E_hat_train
        for i, (_, row) in enumerate(train_df.iterrows()):
            result_rows.append({
                "article_id": row["article_id"],
                "market_id": row["market_id"],
                "shock_embedding": residuals_train[i].tolist(),
                "raw_embedding": np.array(row["analysis_embedding"], dtype=np.float32).tolist(),
                "lambda_chosen": lambda_chosen,
                "category": cat,
                "split": "train",
            })

    return pd.DataFrame(result_rows)
