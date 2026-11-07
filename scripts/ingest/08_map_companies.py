"""Match articles to the study companies with a local LLM: one yes/no question per (article, company) pair.

Runs on Bouchet only (scripts/bouchet/ingest_08_map.sbatch). The model run refuses to start
without a CUDA GPU, so it never downloads the model or generates on a laptop.

    python scripts/ingest/08_map_companies.py --scan         # CPU job: name hits and questions -> data/news/company_map/<prompt_version>/
    python scripts/ingest/08_map_companies.py --limit 1000   # test run on a seeded sample of pairs -> data/news/company_map_test/<prompt_version>/
    python scripts/ingest/08_map_companies.py                # full run, resumes at the first missing chunk
    python scripts/ingest/08_map_companies.py --retry        # ask the pairs that failed again
    python scripts/ingest/08_map_companies.py --build        # yes answers -> matches.parquet, articles.parquet

Reads the articles that still carry text from the fetch shards data/news/fetched/part-*.parquet. A pair
(article, company) is asked when a company name is in the headline or lede, or the company's names appear
at least 3 times in lede and body; names are recomputed from config/companies.yaml (company_map.scan_article).
Pairs are sorted by (article_id, company_id) and cut into chunks of llm_map.chunk_size; chunk k is
data/news/company_map/<prompt_version>/part-<k>.parquet (article_id, company_id, cut, answer, model, prompt_version),
and a rerun skips the chunks that exist. failed.parquet holds the pairs with no valid answer; --retry writes
their answers to retry-*.parquet. prompt.txt holds the exact prompt and schema of that version; a changed
prompt under an old version is refused. One JSON log line per chunk goes to stdout and logs/.
--build keeps the yes answers, drops same-headline same-day duplicates per company (longest body kept)
and writes matches.parquet. It never changes the fetch shards.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import yaml

from src.ingest.body_fetch import article_id, embedding_text, normalize_headline
from src.ingest.companies import load_companies
from src.ingest.company_map import SCHEMA, SYSTEM, article_text, fit_message, parse_answer, prompt_text, scan_article

FETCHED = Path("data/news/fetched")
CFG_CHARS = yaml.safe_load(open("config/ingest.yaml"))["llm_map"]["max_input_chars"]
ARTICLES = Path("data/news/articles.parquet")
OUT = Path("data/news/company_map")  # results live in OUT/<prompt_version>/
OUT_TEST = Path("data/news/company_map_test")
MATCHES = Path("data/news/matches.parquet")
KEY = ["article_id", "company_id"]


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)  # atomic: the file exists whole or not at all


def load_kept(cols: list[str], ids: set | None = None) -> pd.DataFrame:
    """Articles that still carry text in the fetch shards, with article_id; only `ids` if given (read shard by shard)."""
    parts = []
    for p in sorted(FETCHED.glob("part-*.parquet")):
        f = pd.read_parquet(p, columns=list(dict.fromkeys(["url", "body"] + cols)))
        f["article_id"] = f["url"].map(article_id)  # normalized URL, so spellings of one URL are one article
        parts.append(f if ids is None else f[f["article_id"].isin(ids)])
    f = pd.concat(parts, ignore_index=True).drop_duplicates("article_id", keep="last")  # a retry sits in a later shard
    return f[f["body"].notna()].copy()


DROPPED_DOMAINS = ("instagram.com", "facebook.com")  # social pages: name boilerplate, not news


def scan_shard(path: Path) -> list[tuple]:
    """Per article in one shard: (article_id, [(company_id, asked)], asked pairs, (headline, cut text, cut) or None).
    Old training-period rows and Instagram/Facebook pages count as having no text."""
    companies = load_companies()
    f = pd.read_parquet(path, columns=["url", "period", "headline", "lede", "body"])
    out = []
    for u, per, h, l, b in zip(f["url"], f["period"], f["headline"], f["lede"], f["body"]):
        a = article_id(u)
        host = urlparse(u).netloc.lower()
        if not isinstance(b, str) or per == "training" or any(host == d or host.endswith("." + d) for d in DROPPED_DOMAINS):
            out.append((a, [], [], None))
            continue
        h, l = [x if isinstance(x, str) else "" for x in (h, l)]  # parquet nulls can be NaN
        hits = scan_article(h, l, b, companies)
        asked = [q for q in hits if q["asked"]]
        t = article_text(l, b)
        out.append((a, [(q["company_id"], q["asked"]) for q in hits], asked, (h, t[:CFG_CHARS], len(t) > CFG_CHARS) if asked else None))
    return out


def scan(out: Path, workers: int) -> None:
    """CPU step: every name hit (hits.parquet) and every asked pair with its prompt text (questions.parquet)."""
    hits, asked, arts = {}, {}, {}
    with Pool(workers) as pool:
        for rows in pool.imap(scan_shard, sorted(FETCHED.glob("part-*.parquet")), chunksize=4):  # shard order kept
            for a, hs, qs, art in rows:  # a later shard's copy (a retry) replaces an earlier one, as in load_kept
                hits.pop(a, None), asked.pop(a, None), arts.pop(a, None)
                if hs:
                    hits[a] = hs
                if qs:
                    asked[a], arts[a] = qs, art
    out.mkdir(parents=True, exist_ok=True)
    write_parquet(pd.DataFrame([(a, c, k) for a, hs in hits.items() for c, k in hs], columns=["article_id", "company_id", "asked"]),
                  out / "hits.parquet")
    q = pd.DataFrame([{"article_id": a, **p, "headline": arts[a][0], "text": arts[a][1], "was_cut": arts[a][2]}
                      for a, ps in asked.items() for p in ps])
    q = q[KEY + ["company", "names", "in_head", "mentions", "headline", "text", "was_cut"]].sort_values(KEY).reset_index(drop=True)
    write_parquet(q, out / "questions.parquet")
    print(f"{len(hits)} articles with a name hit, {len(q)} questions over {len(asked)} articles -> {out}", flush=True)


def read_answers(out: Path) -> pd.DataFrame:
    """Every answer under out (chunks and retries); a later file wins for a repeated pair."""
    parts = sorted(out.glob("part-*.parquet")) + sorted(out.glob("retry-*.parquet"))
    if not parts:
        sys.exit(f"no answers in {out}")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True).drop_duplicates(KEY, keep="last")


def gpu_used_gb() -> float:
    import torch

    free, total = torch.cuda.mem_get_info()  # device-wide, so it includes the vLLM engine process
    return round((total - free) / 2**30, 1)


def prepare_out(out: Path) -> None:
    """Create the version folder and save its prompt; refuse a changed prompt under the same version."""
    out.mkdir(parents=True, exist_ok=True)
    saved = out / "prompt.txt"
    if saved.exists() and saved.read_text() != prompt_text():
        sys.exit(f"{saved} differs from the current prompt or schema: bump llm_map.prompt_version")
    if not saved.exists():
        saved.write_text(prompt_text())


def run(cfg: dict, out: Path, limit: int | None, retry: bool) -> None:
    import torch

    if not torch.cuda.is_available():
        sys.exit("no CUDA GPU: the company mapping runs on Bouchet only")
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    pairs = pd.read_parquet(OUT / out.name / "questions.parquet")  # written by --scan, always under OUT
    if limit:
        pairs = pairs.sample(n=min(limit, len(pairs)), random_state=cfg["seed"]).sort_values(KEY).reset_index(drop=True)
    print(f"{len(pairs)} pairs over {pairs['article_id'].nunique()} articles", flush=True)

    prepare_out(out)
    failed_path = out / "failed.parquet"
    failed = pd.read_parquet(failed_path) if failed_path.exists() else pd.DataFrame(columns=KEY + ["error"])
    size = cfg["chunk_size"]
    if retry:
        todo = pairs.merge(failed[KEY], on=KEY)
        k0 = len(list(out.glob("retry-*.parquet")))
        chunks = [(f"retry-{k0 + i:05d}", todo.iloc[j:j + size]) for i, j in enumerate(range(0, len(todo), size))]
    else:
        chunks = [(f"part-{i:05d}", pairs.iloc[j:j + size]) for i, j in enumerate(range(0, len(pairs), size))
                  if not (out / f"part-{i:05d}.parquet").exists()]
    n_total = sum(len(c) for _, c in chunks)
    if not chunks:
        print("nothing to do")
        return

    tok = AutoTokenizer.from_pretrained(cfg["model"])
    sys_tokens = len(tok(SYSTEM, add_special_tokens=False)["input_ids"])
    params = SamplingParams(temperature=cfg["temperature"], seed=cfg["seed"], max_tokens=cfg["max_output_tokens"],
                            structured_outputs=StructuredOutputsParams(json=SCHEMA))
    llm = LLM(model=cfg["model"], enable_prefix_caching=True, seed=cfg["seed"],
              max_model_len=sys_tokens + cfg["max_input_tokens"] + cfg["max_output_tokens"] + 64)
    logf = open(Path("logs") / f"{out.parent.name}_{out.name}.log", "a")
    t_start, n_done, tok_in, tok_out = time.time(), 0, 0, 0
    for name, chunk in chunks:
        t0 = time.time()
        cache, convs, cut = {}, [], []
        for p in chunk.to_dict("records"):
            msg, c = fit_message(p, p["headline"], p["text"], tok, cfg["max_input_tokens"], cache)
            c = c or p["was_cut"]
            convs.append([{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}])
            cut.append(c)
        rows, errs, c_in, c_out = [], [], 0, 0
        try:
            res = llm.chat(convs, params, chat_template_kwargs={"enable_thinking": False}, use_tqdm=False)
        except Exception as e:  # generation error: the whole chunk is retried with --retry
            res = []
            errs = [{"article_id": a, "company_id": c, "error": f"generation: {type(e).__name__}: {e}"[:300]}
                    for a, c in zip(chunk["article_id"], chunk["company_id"])]
        for j, o in enumerate(res):
            a, c = chunk["article_id"].iloc[j], chunk["company_id"].iloc[j]
            c_in += len(o.prompt_token_ids)
            c_out += len(o.outputs[0].token_ids)
            try:
                if o.outputs[0].finish_reason == "length":
                    raise ValueError("output_truncated")
                ans = parse_answer(o.outputs[0].text)
            except ValueError as e:
                errs.append({"article_id": a, "company_id": c, "error": str(e)[:300]})
                continue
            rows.append({"article_id": a, "company_id": c, "cut": cut[j], "answer": ans,
                         "model": cfg["model"], "prompt_version": str(cfg["prompt_version"])})
        if rows:
            write_parquet(pd.DataFrame(rows), out / f"{name}.parquet")
        done = pd.DataFrame(rows)[KEY] if rows else pd.DataFrame(columns=KEY)
        left = failed.merge(done, on=KEY, how="left", indicator=True).query("_merge == 'left_only'").drop(columns="_merge")
        failed = pd.concat([left, pd.DataFrame(errs, columns=KEY + ["error"])], ignore_index=True).drop_duplicates(KEY, keep="last")
        write_parquet(failed, failed_path)

        n_done += len(chunk)
        tok_in += c_in
        tok_out += c_out
        rate = n_done / (time.time() - t_start)
        line = json.dumps({
            "chunk": name, "done": n_done, "remaining": n_total - n_done, "pairs_per_s": round(rate, 2),
            "eta_min": round((n_total - n_done) / rate / 60, 1), "input_tokens": c_in, "output_tokens": c_out,
            "gpu_gb": gpu_used_gb(),
            "yes_share": round(sum(r["answer"] == "yes" for r in rows) / len(rows), 3) if rows else None,
            "cut": sum(r["cut"] for r in rows), "failed": len(errs), "chunk_s": round(time.time() - t0, 1),
        })
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    if limit:
        secs = time.time() - t_start
        print(f"\nfull run (excludes model load): {secs / n_done * len(pairs) / 3600:.1f} h at this rate, "
              f"total input tokens {tok_in}, output tokens {tok_out}, failed pairs {len(failed)}")


def build(out: Path) -> None:
    yes = read_answers(out)
    yes = yes[yes["answer"] == "yes"]
    art = load_kept(["headline", "lede", "day", "source", "period"], set(yes["article_id"]))
    m = yes.merge(art[["article_id", "url", "headline", "lede", "body", "day"]], on="article_id")
    m["_h"] = m["headline"].map(normalize_headline)
    m["_len"] = m["lede"].fillna("").str.len() + m["body"].str.len()
    m = m.sort_values(["_len", "url"], ascending=[False, True])
    dup = m.duplicated(["company_id", "day", "_h"]) & (m["_h"] != "")  # same headline, same day, same company: keep the longest
    m = m[~dup].sort_values(KEY).reset_index(drop=True)
    write_parquet(m[["article_id", "url", "company_id", "cut", "model", "prompt_version"]], MATCHES)

    a = art[art["article_id"].isin(m["article_id"])].reset_index(drop=True)  # one row per matched article, read by script 07
    a["text"] = [embedding_text(h, l, b, s, d) for h, l, b, s, d in zip(a["headline"], a["lede"], a["body"], a["source"], a["day"])]
    a["timestamp_precision"] = "day"
    write_parquet(a[["article_id", "url", "period", "day", "source", "headline", "lede", "body", "text",
                     "timestamp_precision"]], ARTICLES)
    print(f"{len(m)} matches ({int(dup.sum())} same-headline duplicates removed) over {len(a)} articles "
          f"-> {MATCHES}, {ARTICLES}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--retry", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--scan", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load(open("config/ingest.yaml"))["llm_map"]
    pv = str(cfg["prompt_version"])
    Path("logs").mkdir(exist_ok=True)

    if args.scan:
        scan(OUT / pv, int(os.environ.get("SLURM_CPUS_PER_TASK", "1")))
        return
    if args.build:
        build(OUT / pv)
        return
    run(cfg, (OUT_TEST if args.limit else OUT) / pv, args.limit, args.retry)


if __name__ == "__main__":
    main()
