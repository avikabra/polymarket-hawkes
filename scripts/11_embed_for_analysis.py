"""Script 11: Compute analysis embeddings for verified articles only.

Uses AnalysisEmbedder (E5-large, float32) on title+lede+body_text.
Reads model from config/analysis.yaml.
Writes float32 Parquet to data/news/analysis_embeddings/.

Run this AFTER script 09 (LLM verification) and script 06 (body fetch).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.matching.embedder import AnalysisEmbedder
from src.utils import get_logger

DB_PATH = Path("data/matches/matches.db")
BODIES_DIR = Path("data/news/bodies")
GDELT_DIR = Path("data/news/gdelt_gkg")
FEEDS_DIR = Path("data/news/feeds")
ANALYSIS_EMB_DIR = Path("data/news/analysis_embeddings")

log = get_logger(__name__)


def _load_config() -> dict:
    cfg_path = Path("config/analysis.yaml")
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f)
    return {}


def _load_article_meta() -> pd.DataFrame:
    parts = []
    for d in [GDELT_DIR, FEEDS_DIR]:
        if not d.exists():
            continue
        paths = list(d.rglob("*.parquet"))
        if paths:
            parts.append(pa.concat_tables([pq.read_table(p) for p in paths]).to_pandas())
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    return df.drop_duplicates(subset=["article_id"])


def _enrich_bodies(df: pd.DataFrame) -> pd.DataFrame:
    """Add body_text column by reading from data/news/bodies/{article_id}.txt."""
    def _read_body(article_id: str) -> str | None:
        p = BODIES_DIR / f"{article_id}.txt"
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8").strip()
        return text if text else None

    df = df.copy()
    df["body_text"] = df["article_id"].apply(_read_body)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="Encoding batch size. Use 256+ on Colab/GPU."
    )
    args = parser.parse_args()

    ANALYSIS_EMB_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        print("No matches.db — run script 09 first.")
        return

    # Get verified article IDs
    conn = sqlite3.connect(DB_PATH)
    verified_ids = {
        row[0] for row in conn.execute(
            "SELECT DISTINCT article_id FROM verifications WHERE is_match=1"
        ).fetchall()
    }
    conn.close()

    if not verified_ids:
        print("No verified articles found.")
        return

    log.info("verified articles to embed", count=len(verified_ids))

    # Load article metadata
    meta_df = _load_article_meta()
    if meta_df.empty:
        print("No article metadata found.")
        return

    articles_df = meta_df[meta_df["article_id"].isin(verified_ids)].copy()
    articles_df = _enrich_bodies(articles_df)

    # Load config
    cfg = _load_config()
    emb_cfg = cfg.get("analysis_embedding", {})
    model_name = emb_cfg.get("model", "intfloat/e5-large-v2")
    max_body_chars = int(emb_cfg.get("max_body_chars", 2048))

    log.info("analysis embedding", model=model_name, articles=len(articles_df))

    embedder = AnalysisEmbedder(model_name=model_name, max_body_chars=max_body_chars, batch_size=args.batch_size)
    emb_df = embedder.embed_articles(articles_df)

    out_path = ANALYSIS_EMB_DIR / "analysis_embeddings.parquet"
    pq.write_table(pa.Table.from_pandas(emb_df), out_path)
    (ANALYSIS_EMB_DIR / "_SUCCESS").touch()

    headline_only = (emb_df["embedding_source"] == "headline_only").sum()
    full_text = (emb_df["embedding_source"] == "full_text").sum()
    print(f"Embedded: {len(emb_df)} articles")
    print(f"  full_text:     {full_text} ({100*full_text/max(len(emb_df),1):.1f}%)")
    print(f"  headline_only: {headline_only} ({100*headline_only/max(len(emb_df),1):.1f}%)")


if __name__ == "__main__":
    main()
