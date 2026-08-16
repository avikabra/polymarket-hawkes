---
name: project-run-state
description: Current pipeline run state — script 07 overnight embedding run
metadata:
  type: project
---

Script 07 (BGE embedding) is running as PID 26063, started 2026-07-11 at 03:55 UTC.

**Configuration:**
- batch_size=128 (safe for 8 GB unified memory; 512 causes MPS OOM)
- 96 chunks × 5000 articles, incremental checkpointing to `data/news/matching_embeddings/_chunks/`
- Estimated run time: ~11 hours (completes ~2026-07-11 15:00 UTC ≈ 8 AM local)
- Log: `logs/07_embed.log`

**Why:** batch=512 hangs indefinitely on this machine when corpus is in memory simultaneously (MPS attention matrices exceed available GPU memory). batch=128 benchmarked at 12.1 texts/sec.

**Key fixes made in this session:**
- `src/news/normalizer.py`: GDELT title = URL → replaced with entity+theme semantic text (vectorized)  
- `src/matching/embedder.py`: offline env vars baked in, incremental chunk-write with resume
- `scripts/07_embed_for_matching.py`: corpus loaded BEFORE model (avoids unified-memory contention)

**How to apply:** When script 07 completes, run scripts 08→14 in sequence to produce `shock_embeddings.parquet`. Script 08 next: `uv run python scripts/08_match_candidates.py`
