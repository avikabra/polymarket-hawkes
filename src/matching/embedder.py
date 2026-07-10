from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer

from src.utils import get_logger

DEFAULT_MODEL = "BAAI/bge-large-en-v1.5"
EMBED_DIM = 1024

DEFAULT_ANALYSIS_MODEL = "intfloat/e5-large-v2"
ANALYSIS_EMBED_DIM = 768


class BGEEmbedder:
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str = "auto",
        batch_size: int = 64,
    ) -> None:
        import torch
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = SentenceTransformer(model_name, device=device)
        self._batch_size = batch_size
        self._log = get_logger(__name__)

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        )
        return vecs.astype(np.float16)

    def embed_articles(
        self,
        articles_df: pd.DataFrame,
        existing_parquet_path: str | None = None,
    ) -> pd.DataFrame:
        existing_ids: set[str] = set()
        existing_rows: list[dict] = []
        if existing_parquet_path and Path(existing_parquet_path).exists():
            existing = pq.read_table(existing_parquet_path).to_pandas()
            existing_ids = set(existing["article_id"].tolist())
            existing_rows = existing.to_dict("records")

        new_df = articles_df[~articles_df["article_id"].isin(existing_ids)]
        if new_df.empty:
            return (
                pd.DataFrame(existing_rows)
                if existing_rows
                else pd.DataFrame(columns=["article_id", "embedding"])
            )

        texts = (
            new_df["title"].fillna("") + " " + new_df["lede"].fillna("")
        ).str.slice(0, 2048).tolist()
        vecs = self.embed_texts(texts)
        new_rows = [
            {"article_id": aid, "embedding": emb.tobytes()}
            for aid, emb in zip(new_df["article_id"].tolist(), vecs)
        ]
        return pd.DataFrame(existing_rows + new_rows)

    def embed_markets(self, universe_df: pd.DataFrame) -> pd.DataFrame:
        texts = (
            universe_df["question"].fillna("") + " " + universe_df["description"].fillna("")
        ).str.slice(0, 2048).tolist()
        vecs = self.embed_texts(texts)
        return pd.DataFrame([
            {"market_id": mid, "embedding": emb.tobytes()}
            for mid, emb in zip(universe_df["market_id"].tolist(), vecs)
        ])


class AnalysisEmbedder:
    """Analysis embedding pass — float32, full text (title+lede+body), E5-large by default.

    Do NOT confuse with BGEEmbedder (matching only). These two embedding passes serve
    different purposes and must not be mixed.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_ANALYSIS_MODEL,
        device: str = "auto",
        batch_size: int = 32,
        max_body_chars: int = 2048,
    ) -> None:
        import torch
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = SentenceTransformer(model_name, device=device)
        self._batch_size = batch_size
        self._max_body_chars = max_body_chars
        self._log = get_logger(__name__)

    def _build_text(self, title: str, lede: str | None, body_text: str | None) -> tuple[str, str]:
        """Return (text_for_embedding, embedding_source)."""
        parts = [title]
        if lede:
            parts.append(lede)
        if body_text:
            parts.append(body_text[: self._max_body_chars])
            source = "full_text"
        else:
            source = "headline_only"
        return " ".join(parts), source

    def embed_articles(self, articles_df: pd.DataFrame) -> pd.DataFrame:
        """Embed verified articles. Returns DataFrame with article_id, embedding (bytes), embedding_source."""
        texts = []
        sources = []
        for _, row in articles_df.iterrows():
            text, source = self._build_text(
                row.get("title", ""),
                row.get("lede") or None,
                row.get("body_text") or None,
            )
            texts.append(text)
            sources.append(source)

        vecs = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        ).astype(np.float32)

        return pd.DataFrame([
            {
                "article_id": aid,
                "embedding": emb.tobytes(),
                "embedding_source": src,
            }
            for aid, emb, src in zip(
                articles_df["article_id"].tolist(), vecs, sources
            )
        ])
