from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer

from src.utils import get_logger

# Suppress tokenizer parallelism warnings (fork-safety on macOS).
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

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
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
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
        chunk_size: int = 5000,
    ) -> pd.DataFrame:
        """Embed articles with incremental checkpointing.

        Writes each chunk to a _chunks/ subdirectory next to existing_parquet_path,
        then merges to existing_parquet_path at the end. Resumable: already-embedded
        article_ids are skipped. A crash loses at most chunk_size articles of work.
        """
        import pyarrow as pa

        pq_path = Path(existing_parquet_path) if existing_parquet_path else None
        chunks_dir = (pq_path.parent / "_chunks") if pq_path else None

        # Collect already-embedded article_ids from final file or chunks
        existing_ids: set[str] = set()
        if pq_path and pq_path.exists():
            existing_ids = set(
                pq.read_table(pq_path, columns=["article_id"]).to_pandas()["article_id"].tolist()
            )
        if chunks_dir and chunks_dir.exists():
            for cp in chunks_dir.glob("*.parquet"):
                existing_ids.update(
                    pq.read_table(cp, columns=["article_id"]).to_pandas()["article_id"].tolist()
                )
        if existing_ids:
            self._log.info("resuming embedding", already_done=len(existing_ids))

        new_df = articles_df[~articles_df["article_id"].isin(existing_ids)].reset_index(drop=True)
        if new_df.empty:
            self._log.info("all articles already embedded")
            return self._merge_chunks(pq_path, chunks_dir)

        total = len(new_df)
        n_chunks = (total + chunk_size - 1) // chunk_size
        self._log.info("embedding articles", total=total, chunks=n_chunks, chunk_size=chunk_size)

        if chunks_dir:
            chunks_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_chunks):
            chunk = new_df.iloc[i * chunk_size : (i + 1) * chunk_size]
            texts = (
                chunk["title"].fillna("") + " " + chunk["lede"].fillna("")
            ).str.slice(0, 2048).tolist()
            vecs = self.embed_texts(texts)
            rows = [
                {"article_id": aid, "embedding": emb.tobytes()}
                for aid, emb in zip(chunk["article_id"].tolist(), vecs)
            ]
            chunk_df = pd.DataFrame(rows)
            if chunks_dir:
                pq.write_table(pa.Table.from_pandas(chunk_df), chunks_dir / f"chunk_{i:05d}.parquet")
            self._log.info("chunk done", chunk=i + 1, of=n_chunks, embedded=len(chunk_df))

        return self._merge_chunks(pq_path, chunks_dir)

    def _merge_chunks(
        self, pq_path: Path | None, chunks_dir: Path | None
    ) -> pd.DataFrame:
        """Merge chunk files into the final parquet and return the combined DataFrame."""
        import pyarrow as pa

        parts: list[pd.DataFrame] = []
        if pq_path and pq_path.exists():
            parts.append(pq.read_table(pq_path).to_pandas())
        if chunks_dir and chunks_dir.exists():
            for cp in sorted(chunks_dir.glob("*.parquet")):
                parts.append(pq.read_table(cp).to_pandas())

        if not parts:
            return pd.DataFrame(columns=["article_id", "embedding"])

        merged = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["article_id"])
        if pq_path:
            pq.write_table(pa.Table.from_pandas(merged), pq_path)
            # Clean up chunks after successful merge
            if chunks_dir and chunks_dir.exists():
                for cp in chunks_dir.glob("*.parquet"):
                    cp.unlink()
                try:
                    chunks_dir.rmdir()
                except OSError:
                    pass
        return merged

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
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
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
