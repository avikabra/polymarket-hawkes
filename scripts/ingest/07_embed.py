"""Steps 19 to 21: embed every article and every company page with Qwen3-Embedding-4B.

Runs on Bouchet only (scripts/bouchet/ingest_07_embed.sbatch). It refuses to start without a
CUDA GPU, so it never downloads the model or embeds on a laptop.

Both sides are embedded as documents, with no query instruction, so article-to-page cosine
compares like with like. Vectors are L2-normalized float32 (2,560 dimensions).

    uv run python scripts/ingest/07_embed.py --what companies
    uv run python scripts/ingest/07_embed.py --what articles      # resumes by shard

Writes data/news/embeddings/companies.{npy,parquet} and
data/news/embeddings/articles/part-*.{npy,parquet}; each .parquet lists the row ids in order.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import yaml

OUT = Path("data/news/embeddings")
SHARD = 20_000


def load_model(name: str, max_tokens: int):
    import torch
    from sentence_transformers import SentenceTransformer

    if not torch.cuda.is_available():
        sys.exit("no CUDA GPU: embeddings run on Bouchet only")
    model = SentenceTransformer(name, device="cuda", model_kwargs={"torch_dtype": torch.bfloat16},
                                tokenizer_kwargs={"padding_side": "left"})
    model.max_seq_length = max_tokens
    return model


def encode(model, texts: list[str], batch_size: int) -> np.ndarray:
    # longest first, so each batch pads to similar lengths; restore the input order after
    order = np.argsort([-len(t) for t in texts], kind="stable")
    vecs = model.encode([texts[i] for i in order], batch_size=batch_size, normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=True).astype(np.float32)
    out = np.empty_like(vecs)
    out[order] = vecs
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", choices=["companies", "articles"], required=True)
    ap.add_argument("--batch-size", type=int, default=None)
    args = ap.parse_args()
    cfg = yaml.safe_load(open("config/ingest.yaml"))["embed"]
    bs = args.batch_size or cfg["batch_size"]

    if args.what == "companies":
        pages = pd.read_parquet("data/news/company_pages.parquet")
        model = load_model(cfg["model"], cfg["max_tokens_company"])
        OUT.mkdir(parents=True, exist_ok=True)
        np.save(OUT / "companies.npy", encode(model, pages["text"].tolist(), max(1, bs // 4)))
        pages[["company_id", "revision_id"]].to_parquet(OUT / "companies.parquet", index=False)
        print(f"{len(pages)} company pages -> {OUT}")
        return

    art = pd.read_parquet("data/news/articles.parquet", columns=["article_id", "text"])
    d = OUT / "articles"
    d.mkdir(parents=True, exist_ok=True)
    model = load_model(cfg["model"], cfg["max_tokens_article"])
    # a shard is done only if both files exist; resume is keyed on article_id, so a re-sorted
    # articles table cannot misalign vectors with ids
    for p in d.glob("part-*.parquet"):
        if not p.with_suffix(".npy").exists():
            p.unlink()  # ids written but the vectors never landed: drop the orphan and redo
    parts = sorted(d.glob("part-*.parquet"))
    done = [pd.read_parquet(p)["article_id"] for p in parts]
    todo = art[~art["article_id"].isin(pd.concat(done) if done else [])]
    k = int(parts[-1].stem.split("-")[1]) + 1 if parts else 0  # never reuse a shard number
    for i in range(0, len(todo), SHARD):
        chunk = todo.iloc[i:i + SHARD]
        vecs = encode(model, chunk["text"].tolist(), bs)
        chunk[["article_id"]].to_parquet(d / f"part-{k:05d}.parquet", index=False)  # ids first
        with open(d / f"part-{k:05d}.npy.tmp", "wb") as f:
            np.save(f, vecs)
        (d / f"part-{k:05d}.npy.tmp").rename(d / f"part-{k:05d}.npy")  # atomic: the shard exists whole or not at all
        print(f"shard {k}: {len(chunk)} articles")
        k += 1

if __name__ == "__main__":
    main()
