"""Dataset classes for W4-6 architecture comparison training."""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

# purging.py's _CAT_ORDER (the full contract_family schema domain) also
# declares "other_ladder" and "other" — these 5 are the categories actually
# observed with real rows in the corpus as of the 2026-09-29 Bouchet run.
# Verify against real data before trusting this list if the universe has
# since been expanded (see novel_math_design.md item 5). Replaces the
# pre-pivot sports/politics/geopolitics taxonomy, which predates the
# Weeks 7-9 company-contract pivot and no longer matches this column.
_CATEGORIES: list[str] = [
    "corporate_event", "price_ladder", "revenue_ladder",
    "valuation_ladder", "market_cap_ladder",
]
CAT_TO_INT: dict[str, int] = {c: i for i, c in enumerate(_CATEGORIES)}
CAT_LABEL: dict[int, str] = {i: c for i, c in enumerate(_CATEGORIES)}

DEFAULT_TARGET = "y_logit_24h"


def _valid_col_for_target(target: str) -> str:
    """Map a y_logit_{delta}h[_ladder] target to its valid_{delta}h column.

    A _ladder column has no separate validity flag of its own — it is only
    meaningful where the underlying valid_{delta}h was already True (see
    src.analysis.ladder_reaction.compute_ladder_adjusted_reactions). Mirrors
    scripts/16_train_linear_baseline.py's identical helper.
    """
    window = target.removeprefix("y_logit_").removesuffix("_ladder")
    return f"valid_{window}"


def _load_and_filter(
    parquet_path: str,
    split: str,
    category_filter: str | None,
    target: str = DEFAULT_TARGET,
) -> pd.DataFrame:
    """Load parquet, filter on split, valid_{target}, and optionally category."""
    df = pd.read_parquet(parquet_path)
    valid_col = _valid_col_for_target(target)
    df = df[df[valid_col] == True].copy()  # noqa: E712
    df = df[df["split"] == split].copy()
    if category_filter is not None and category_filter != "all":
        df = df[df["category"] == category_filter].copy()
    # Coerce nullable fields
    df["parent_event_id"] = df["parent_event_id"].fillna("").astype(str)
    df["news_type"] = df["news_type"].fillna("").astype(str)
    return df.reset_index(drop=True)


class ArticleDataset(Dataset):
    """Flat (non-sequential) dataset for the linear baseline.

    Each item is one article row with its embedding and 6h target.
    """

    def __init__(
        self,
        parquet_path: str,
        split: str,
        embedding_col: str = "shock_embedding",
        category_filter: str | None = None,
        target: str = DEFAULT_TARGET,
    ) -> None:
        self._embedding_col = embedding_col
        self._target = target
        df = _load_and_filter(parquet_path, split, category_filter, target)
        self._rows = df.to_dict("records")

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, idx: int) -> dict:
        row = self._rows[idx]
        emb = np.array(row[self._embedding_col], dtype=np.float32)
        return {
            "embedding": torch.from_numpy(emb),
            # Always keyed "target" regardless of which y_logit_{delta}h[_ladder]
            # column was requested — callers (Trainer, batch_forward, per-script
            # inference loops) read this one key generically.
            "target": torch.tensor(float(row[self._target]), dtype=torch.float32),
            "article_id": str(row["article_id"]),
            "market_id": str(row["market_id"]),
            "category": int(CAT_TO_INT.get(str(row["category"]), 0)),
            "parent_event_id": str(row["parent_event_id"]),
            "news_type": str(row["news_type"]),
            "directional_impact": int(row["directional_impact"]),
        }


class ArticleSequenceDataset(Dataset):
    """Sequential dataset for LSTM / Transformer / TCN models.

    For each target article, the context window includes up to K prior articles
    from the same market (sorted by canonical_ts), left-padded to length K+1.
    """

    def __init__(
        self,
        parquet_path: str,
        split: str,
        K: int,
        tau_max_days: float = 30.0,
        embedding_col: str = "shock_embedding",
        category_filter: str | None = None,
        target: str = DEFAULT_TARGET,
    ) -> None:
        self._K = K
        self._embedding_col = embedding_col
        self._target = target
        self._tau_max = tau_max_days * 86400.0  # seconds

        df = _load_and_filter(parquet_path, split, category_filter, target)

        # Build full market history from the entire parquet (all splits) so that
        # prior context crosses split boundaries correctly.
        full_df = pd.read_parquet(parquet_path)
        full_df["parent_event_id"] = full_df["parent_event_id"].fillna("").astype(str)
        full_df["news_type"] = full_df["news_type"].fillna("").astype(str)

        self._market_history: dict[str, list[dict]] = {}
        for market_id, grp in full_df.groupby("market_id"):
            grp_sorted = grp.sort_values("canonical_ts")
            history = []
            for rec in grp_sorted.to_dict("records"):
                history.append({
                    "article_id": str(rec["article_id"]),
                    "canonical_ts": int(rec["canonical_ts"]),
                    "shock_embedding": rec["shock_embedding"],
                    "raw_embedding": rec["raw_embedding"],
                })
            self._market_history[str(market_id)] = history

        self._rows = df.to_dict("records")

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, idx: int) -> dict:
        row = self._rows[idx]
        market_id = str(row["market_id"])
        target_ts = int(row["canonical_ts"])

        history = self._market_history.get(market_id, [])
        prior = [h for h in history if h["canonical_ts"] < target_ts]
        prior = prior[-self._K:]  # last K

        # Build window: prior articles + target article
        target_entry = {
            "article_id": str(row["article_id"]),
            "canonical_ts": target_ts,
            "shock_embedding": row["shock_embedding"],
            "raw_embedding": row["raw_embedding"],
        }
        window = prior + [target_entry]
        window_len = len(window)
        total_len = self._K + 1

        # Infer embedding dimension from first available entry
        d = len(window[0]["shock_embedding"])

        shock_arr = np.zeros((total_len, d), dtype=np.float32)
        raw_arr = np.zeros((total_len, d), dtype=np.float32)
        mask = np.zeros(total_len, dtype=bool)
        delta_t = np.zeros(total_len, dtype=np.float32)

        pad_len = total_len - window_len
        for i, entry in enumerate(window):
            pos = pad_len + i
            shock_arr[pos] = np.array(entry["shock_embedding"], dtype=np.float32)
            raw_arr[pos] = np.array(entry["raw_embedding"], dtype=np.float32)
            mask[pos] = True
            dt = (target_ts - entry["canonical_ts"]) / self._tau_max
            delta_t[pos] = float(np.clip(dt, 0.0, 1.0))

        return {
            "shock_embeddings": torch.from_numpy(shock_arr),
            "raw_embeddings": torch.from_numpy(raw_arr),
            "mask": torch.from_numpy(mask),
            "timestamps": torch.from_numpy(delta_t),
            "lengths": torch.tensor(window_len, dtype=torch.long),
            "target": torch.tensor(float(row[self._target]), dtype=torch.float32),
            "article_id": str(row["article_id"]),
            "market_id": market_id,
            "category": int(CAT_TO_INT.get(str(row["category"]), 0)),
            "parent_event_id": str(row["parent_event_id"]),
            "news_type": str(row["news_type"]),
            "directional_impact": int(row["directional_impact"]),
        }
