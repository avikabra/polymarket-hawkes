# Colab Offload Plan — What Moves, What Doesn't

*Drafted 2026-09-05 · companion to `notebooks/colab_pipeline.ipynb` and `reports/yale_cluster_request.md`*

## The one thing to be clear about first

**Colab does not unblock the core deliverable.** Q2/Q3 are blocked by a *data-source decision*
(dead Goldsky → which trade feed replaces it — see `reports/trade_source_decision.md`), not by a
compute limit. Running on Colab or the cluster changes *where* trades get pulled and bars get built,
not *whether* we have a source to pull from. So the sequencing stands: **decide the source (needs
Bryan) → then the heavy lifting runs, on Colab now or the cluster later.**

## Split of labour

| Half | Scripts | Bound by | Where it runs |
|---|---|---|---|
| **Front half (data acquisition)** | 01 universe · 02 trades · 03 bars · 04 GDELT · 05 feeds · 06 bodies | network / disk I/O | local laptop **or** cluster login/transfer node; upload parquet to Drive |
| **EDA** | `eda_logodds.py` | CPU + plotting | anywhere once bars (03) exist |
| **Back half (embedding-heavy)** | 07 BGE · 08 FAISS · 09 verify · 10 dedup · 11 E5 · 12–14 | **GPU** | **Colab (already wired)** → cluster GPU when allocation lands |

`notebooks/colab_pipeline.ipynb` (34 cells) already implements the back half end-to-end: mount
Drive → install CUDA torch → run 07→14 → save results back to Drive. That is the ~11 h local BGE
pass reduced to well under an hour on a Colab/cluster GPU.

## Gaps to close before a full Colab run (post-Bryan)

1. **Trade source** — the notebook assumes bars already exist; it starts at 07. Front-half scripts
   02/03 must first run against the *chosen* trade source and their parquet uploaded to Drive.
2. **Matching refactor** — script 07's corpus should reflect the metadata-first matching the advisor
   asked for; that refactor (candidate pre-filter before embeddings) is still pending.
3. **EDA cell** — add an `eda_logodds.py` cell to the notebook so the five log-odds visuals render in
   Colab on the company bars (trivial; the script is parameterized and already smoke-tested).
4. **Universe/EDA are cheap** — 01 and the EDA don't need Colab at all; keep them local.

## Bottom line for tonight

Nothing heavy is worth running before the source decision. The write-up + the Bryan email + the
cluster request are the right use of the night; the Colab notebook is ready to carry the GPU work the
moment the upstream decision unblocks it.
