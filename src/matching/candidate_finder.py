from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.matching.faiss_index import load_index, search


def _load_meta_df(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.is_dir():
        paths = list(p.rglob("*.parquet"))
        if not paths:
            return pd.DataFrame(columns=["article_id", "published_at", "timestamp_precision"])
        return pa.concat_tables([pq.read_table(fp) for fp in paths]).to_pandas()
    if not p.exists():
        return pd.DataFrame(columns=["article_id", "published_at", "timestamp_precision"])
    return pq.read_table(path).to_pandas()


def _parse_gdelt_date(raw_meta_json: str) -> datetime | None:
    try:
        meta = json.loads(raw_meta_json)
        date_int = str(meta.get("date_int", ""))
        if len(date_int) >= 8:
            return datetime(
                int(date_int[:4]), int(date_int[4:6]), int(date_int[6:8]),
                tzinfo=timezone.utc,
            )
    except Exception:
        pass
    return None


class CandidateFinder:
    def __init__(
        self,
        faiss_index_path: str,
        article_id_index_path: str,
        article_meta_path: str,
        k: int = 150,
    ) -> None:
        self._k = k
        self._index: faiss.IndexFlatIP = load_index(faiss_index_path)

        id_df = pq.read_table(article_id_index_path).to_pandas()
        self._row_to_id: dict[int, str] = dict(
            zip(id_df["faiss_row"].tolist(), id_df["article_id"].tolist())
        )

        meta_df = _load_meta_df(article_meta_path)
        has_raw_meta = "raw_metadata_json" in meta_df.columns
        self._meta: dict[str, dict] = {}

        for row in meta_df.to_dict("records"):
            aid = row["article_id"]
            pub_at = row.get("published_at")
            if pub_at is not None and pd.notna(pub_at):
                pub_at = pd.Timestamp(pub_at).to_pydatetime()
                if pub_at.tzinfo is None:
                    pub_at = pub_at.replace(tzinfo=timezone.utc)
            else:
                pub_at = None

            gdelt_date: datetime | None = None
            if has_raw_meta:
                raw = row.get("raw_metadata_json")
                if isinstance(raw, str) and raw:
                    gdelt_date = _parse_gdelt_date(raw)

            self._meta[aid] = {
                "published_at": pub_at,
                "timestamp_precision": str(row.get("timestamp_precision", "unknown")),
                "gdelt_date": gdelt_date,
            }

    def find_candidates(
        self,
        market_id: str,
        market_embedding: np.ndarray,
        window_start: datetime,
        window_end: datetime,
    ) -> list[dict]:
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=timezone.utc)
        if window_end.tzinfo is None:
            window_end = window_end.replace(tzinfo=timezone.utc)

        retrieve_k = min(self._k * 5, self._index.ntotal)
        if retrieve_k == 0:
            return []

        scores, indices = search(self._index, market_embedding, k=retrieve_k)

        candidates: list[dict] = []
        for score, row_idx in zip(scores[0], indices[0]):
            if row_idx < 0:
                continue
            article_id = self._row_to_id.get(int(row_idx))
            if article_id is None:
                continue
            meta = self._meta.get(article_id)
            if meta is None:
                continue

            pub_at: datetime | None = meta["published_at"]
            gdelt_date: datetime | None = meta["gdelt_date"]

            if pub_at is not None:
                in_window = window_start <= pub_at <= window_end
            elif gdelt_date is not None:
                day_start = gdelt_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = gdelt_date.replace(hour=23, minute=59, second=59, microsecond=0)
                in_window = day_start <= window_end and day_end >= window_start
            else:
                in_window = False

            if not in_window:
                continue

            candidates.append({
                "market_id": market_id,
                "article_id": article_id,
                "embedding_score": float(score),
                "article_published_at": pub_at.isoformat() if pub_at is not None else None,
                "timestamp_precision": meta["timestamp_precision"],
            })

            if len(candidates) >= self._k:
                break

        return candidates
