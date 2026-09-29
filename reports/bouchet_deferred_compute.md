# Bouchet-Deferred Compute — Matching Embeddings & LLM Judge

*Weeks 7-9 Task A/B · drafted 2026-09-20 · status: **Script 07 (matching embeddings) COMPLETE as of
2026-09-28 on Bouchet. LLM judge (script 09 `--openweight`) still pending a vLLM/TGI endpoint.***

## Script 07 — done, 2026-09-28

Ran on Bouchet (`gpu` partition, NVIDIA L40S 46GB, account `pi_btk22`, job 27786462) from
`/nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket` (see `reports/bouchet_login_howto.md` for
the environment setup). Verified output:
```
Articles embedded: 546657
Groups embedded:   628
Embedding matrix shape: (546657, 1024)
FAISS index total vectors: 546657
```
Matches the expected cardinality exactly (628 contract groups, per §2 below).

**Gotcha worth remembering:** the first submission (job 27784355) silently ran *stale* code — the
public `git clone` pulled GitHub's `main`, which was 4 commits behind local `weeks-7-9-data-review`
(the group-keyed rewrite, commit `a213195`, had never been pushed). It completed "successfully" but
wrote the old `market_embeddings.parquet` schema (6,928 markets) instead of `group_embeddings.parquet`
(628 groups) — caught by the sbatch script's own row-count verification step. Fixed by pushing the
branch and `git checkout weeks-7-9-data-review` on Bouchet. **Always confirm the remote/branch a
cluster clone tracks matches what you think you tested locally** — a clean job exit is not proof the
right code ran.

Batch size used: 256 (the `--max-chunks`/`--batch-size` guidance below was followed — did not reuse
the local MPS ceiling of 128).

Supersedes the earlier `reports/llm_judge_deferred.md` (renamed/broadened): that file covered only
the LLM judge. Two compute-heavy stages are now deferred to the same cluster access request, not
one — this report covers both.

---

## 1. Why both stages moved to Bouchet, not Colab, not local

- **Hard constraint (unchanged):** no local LLM inference (would crash this 8GB machine), no
  hosted-API pilot calls. Governs the LLM-judge stage.
- **Script 07 (BGE/group embedding pass) decision:** the user chose to wait for Bouchet rather
  than use the Colab handoff that was prepared as a fallback. Both heavy stages now share one
  blocker — Bouchet access — rather than being split across Colab (embeddings) and Bouchet
  (judge). Access is a 1–2 business day turnaround once Prof. Kelly confirms the YCRC request
  (`reports/yale_cluster_request.md`); nothing here is computationally hard, only currently
  inaccessible without crashing this machine or spending unnecessary hosted-API budget on a stage
  about to have free GPU access.

**No Colab prep was carried out or left partially done** — the moment this instruction landed I
stopped without editing `notebooks/colab_pipeline.ipynb` or `scripts/make_colab_zip.sh`; nothing
needs to be discarded (verified via `git status` — both files show no changes).

---

## 2. What's ready and waiting, exactly

| Artifact | State | Verified how |
|---|---|---|
| GDELT corpus | **546,543 rows**, 86 companies, 32 months (2024-01 → 2026-08), on disk at `data/news/gdelt_gkg/` with `_SUCCESS` + `_SCOPE.json` | Read directly off disk 2026-09-20 (Task A, script 04 real run) |
| RSS/feed corpus | 115 minute-precision rows, on disk at `data/news/feeds/` (script 05, pre-existing, untouched this session) | Read directly off disk |
| Group-level embedding code | `BGEEmbedder.embed_groups` + `_build_group_text` in `src/matching/embedder.py`; `scripts/07_embed_for_matching.py` rewired to call it, writes `data/news/matching_embeddings/group_embeddings.parquet` (renamed from `market_embeddings.parquet`) | Unit-tested: `tests/test_embedder.py -k build_group_text`, 4/4 pass, no model load. Not run end-to-end (needs the model + GPU-scale time) |
| Shared matching-text normalizer | `build_matching_text_corpus()` in `src/news/normalizer.py`, used by scripts 07/08/09/12 | 6/6 tests pass (`tests/test_normalizer.py`) |
| `matches.db` | **Does not exist yet** — A0 moved the stale pre-pivot db to `matches.db.stale_may2026.bak`; the schema-v2 DDL lives in `scripts/08_match_candidates.py::_DDL` as code but has never been executed, since script 08 is gated on `group_embeddings.parquet` existing first | `ls data/matches/` — only the `.bak` file present, confirmed 2026-09-20 |
| Rule-based verifier (interim judge) | `src/matching/rule_verifier.py`, unchanged logic; scoring bug fixed upstream (A3: now scores the real synthetic GDELT title / real RSS title, not a bare-URL placeholder) | 13/13 tests pass (`tests/test_rule_verifier.py`, `tests/test_candidate_finder.py`) |
| Open-weight LLM judge | `src/matching/openweight_verifier.py` — mirrors `llm_verifier.py`, uses `openai.AsyncOpenAI`, no default `base_url` (raises `RuntimeError` pointing at `config/openweight_llm.yaml.template` if unconfigured) | 10/10 tests pass (`tests/test_openweight_verifier.py`), mocks only, zero real network calls |
| `config/openweight_llm.yaml.template` | Created, documents `base_url`/`model`/`api_key_env_var` keys | — |

**Correction to the brief I was given:** `matches.db` is not "just the empty DDL with no rows" —
it does not exist as a file at all right now. The DDL is real, tested code, but nothing has
executed `CREATE TABLE` yet because script 08 (which does that) requires `group_embeddings.parquet`
as a prerequisite and exits early with "Missing prerequisite" if it's absent. This doesn't change
the plan — script 08 will create the schema-v2 db on its first real run — just flagging the
inaccuracy rather than letting it stand.

---

## 3. Exact invocation once Bouchet access lands

### 3a. Script 07 — group/article matching embeddings

```bash
uv run python scripts/07_embed_for_matching.py --batch-size <N>
```

**No hardcoded batch size recommendation** — this is a tunable that depends on the actual GPU
Bouchet allocates (`reports/yale_cluster_request.md` lists RTX 5000 Ada / H100 / H200 / B200 as
possible hardware; VRAM varies 32–141GB+). The only fixed local number is `128`, which is a
measured *Apple Silicon MPS* ceiling (`memory/bgp_embedding_run.md`: 512 causes an MPS hang on
this machine) — it does not apply to cluster CUDA hardware and should not be reused as a guess.
Determine the right value empirically on the allocated node (start conservative, e.g. 256, watch
for OOM, increase) rather than assuming a number.

The script is resumable via `--max-chunks` / the `_chunks/` checkpoint directory if a session is
interrupted (same mechanism already used for the Colab fallback that's no longer needed).

Verify:
```bash
uv run python -c "import pandas as pd; df=pd.read_parquet('data/news/matching_embeddings/group_embeddings.parquet'); assert len(df)==628, len(df); print('OK', df.shape)"
```

### 3b. Open-weight LLM judge (after 07 → 08 → 09-rule-based have all run)

1. Copy `config/openweight_llm.yaml.template` → `config/openweight_llm.yaml`, fill in `base_url`
   (the vLLM/TGI/SGLang OpenAI-compatible endpoint Bouchet exposes), `model`, `api_key_env_var`.
2. Cheap, targeted pass first — only what the rule-based judge couldn't confidently resolve:
   ```bash
   uv run python scripts/09_llm_verify_matches.py --openweight --only-low-confidence
   ```
3. Full re-verification only if capacity allows:
   ```bash
   uv run python scripts/09_llm_verify_matches.py --openweight
   ```

Both stages can run in the same Bouchet session/allocation back to back (07 first, since 08/09
depend on its output) — there's no reason to request access twice.

---

## 4. What's still blocked behind these two stages

Candidate generation (script 08), rule-based verification (script 09, no flag), dedup (script 10),
body-fetch (script 06 `--verified-only`) — none of these can run for real until
`group_embeddings.parquet` exists. This was already true before this instruction; it stays true.
The `review_status` histogram and body-fetch success rate that a prior draft of this report was
meant to record remain unavailable until the Bouchet round-trip for script 07 completes and script
09 is run for real.
