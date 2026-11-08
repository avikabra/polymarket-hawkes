"""Match articles to the study companies with a local LLM: one question per article, "which companies is it about?".

Runs on Bouchet only (scripts/bouchet/ingest_08_map.sbatch). The model run refuses to start
without a CUDA GPU, so it never downloads the model or generates on a laptop.

    python scripts/ingest/08_map_companies.py --scan         # CPU job: one question per article -> data/news/company_map/<prompt_version>/
    python scripts/ingest/08_map_companies.py --limit 1000   # test run on a seeded sample of articles -> data/news/company_map_test/<prompt_version>/
    python scripts/ingest/08_map_companies.py                # full run, resumes at the first missing chunk
    python scripts/ingest/08_map_companies.py --retry        # ask the articles that failed again
    python scripts/ingest/08_map_companies.py --build        # answers -> matches.parquet, articles.parquet

Reads the articles that still carry text from the fetch shards data/news/fetched/part-*.parquet. Every article
in which any study company's name appears is asked once, with the list of all 61 companies, the names found and
their counts in the headline and text, and the lede and body cut to llm_map.max_input_chars (flagged); the
model names the companies the article is primarily about, or none (company_map). No count decides who is asked. The GPU job reads questions.parquet one chunk of llm_map.chunk_size articles at a
time, in file order; chunk k is
data/news/company_map/<prompt_version>/part-<k>.parquet (article_id, companies, cut, model, prompt_version),
and a rerun skips the chunks that exist. failed.parquet holds the articles with no valid answer; --retry writes
their answers to retry-*.parquet. prompt.txt holds the exact prompt and schema of that version; a changed
prompt under an old version is refused. One JSON log line per chunk goes to stdout and logs/.
--build keeps the named companies, drops same-headline same-day duplicates per company (longest body kept)
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
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.ingest.body_fetch import article_id, embedding_text, normalize_headline
from src.ingest.companies import load_companies
from src.ingest.company_map import article_text, fit_message, name_hits, parse_answer, prompt_text, schema, system_prompt

FETCHED = Path("data/news/fetched")
CFG_CHARS = yaml.safe_load(open("config/ingest.yaml"))["llm_map"]["max_input_chars"]
ARTICLES = Path("data/news/articles.parquet")
T_PROC = time.time()  # process start, for --stop-after
OUT = Path("data/news/company_map")  # results live in OUT/<prompt_version>/
OUT_TEST = Path("data/news/company_map_test")
MATCHES = Path("data/news/matches.parquet")
KEY = ["article_id", "company_id"]  # one match


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
    """Per article in one shard: (article_id, question or None); a question is (name hits, headline, text).
    Old training-period rows and Instagram/Facebook pages count as having no text."""
    companies = load_companies()
    f = pd.read_parquet(path, columns=["url", "period", "headline", "lede", "body"])
    out = []
    for u, per, h, l, b in zip(f["url"], f["period"], f["headline"], f["lede"], f["body"]):
        a = article_id(u)
        host = urlparse(u).netloc.lower()
        if not isinstance(b, str) or per == "training" or any(host == d or host.endswith("." + d) for d in DROPPED_DOMAINS):
            out.append((a, None))
            continue
        h, l = [x if isinstance(x, str) else "" for x in (h, l)]  # parquet nulls can be NaN
        hits = name_hits(h, l, b, companies)
        t = article_text(l, b)
        out.append((a, (json.dumps(hits), h, t[:CFG_CHARS], len(t) > CFG_CHARS) if hits else None))
    return out


def scan(out: Path, workers: int) -> None:
    """CPU step: one question per article with any company name (questions.parquet).
    Pass 1 notes which shard holds each article's last copy (a retry sits in a later shard, as in load_kept);
    pass 2 writes those rows shard by shard, so only a block of about 20,000 questions is in memory at a time."""
    shards = sorted(FETCHED.glob("part-*.parquet"))
    last = {}
    with Pool(workers) as pool:
        for i, rows in enumerate(pool.imap(scan_shard, shards, chunksize=4)):  # shard order kept
            for a, q in rows:
                last[a] = i if q else None
    out.mkdir(parents=True, exist_ok=True)
    tmp, n = out / "questions.parquet.tmp", 0
    cols = ["article_id", "hits", "headline", "text", "was_cut"]
    writer = pq.ParquetWriter(tmp, pa.schema([("article_id", pa.string()), ("hits", pa.string()), ("headline", pa.string()),
                                              ("text", pa.string()), ("was_cut", pa.bool_())]))
    buf = []
    with Pool(workers) as pool:
        for i, rows in enumerate(pool.imap(scan_shard, shards, chunksize=4)):
            keep = [(a, *q) for a, q in rows if q and last.get(a) == i]
            last.update({a: -1 for a, *_ in keep})  # an article repeated inside one shard is written once
            buf += keep
            if len(buf) >= 20000:  # written in blocks of about 20,000 articles (about 60 MB), so GPU chunks stay full
                writer.write_table(pa.Table.from_pandas(pd.DataFrame(buf, columns=cols), preserve_index=False))
                n, buf = n + len(buf), []
    if buf:
        writer.write_table(pa.Table.from_pandas(pd.DataFrame(buf, columns=cols), preserve_index=False))
        n += len(buf)
    writer.close()
    os.replace(tmp, out / "questions.parquet")
    print(f"{n} questions (articles with a company name) -> {out}", flush=True)


def read_answers(out: Path) -> pd.DataFrame:
    """Every answer under out (chunks and retries); a later file wins for a repeated article."""
    parts = sorted(out.glob("part-*.parquet")) + sorted(out.glob("retry-*.parquet"))
    if not parts:
        sys.exit(f"no answers in {out}")
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True).drop_duplicates("article_id", keep="last")


def gpu_used_gb() -> float:
    import torch

    free, total = torch.cuda.mem_get_info()  # device-wide, so it includes the vLLM engine process
    return round((total - free) / 2**30, 1)


def prepare_out(out: Path) -> None:
    """Create the version folder and save its prompt; refuse a changed prompt under the same version."""
    out.mkdir(parents=True, exist_ok=True)
    saved = out / "prompt.txt"
    if saved.exists() and saved.read_text() != prompt_text(load_companies()):
        sys.exit(f"{saved} differs from the current prompt or schema: bump llm_map.prompt_version")
    if not saved.exists():
        saved.write_text(prompt_text(load_companies()))


def run(cfg: dict, out: Path, limit: int | None, retry: bool, stop_after: float | None = None) -> None:
    import torch

    if not torch.cuda.is_available():
        sys.exit("no CUDA GPU: the company mapping runs on Bouchet only")
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    path = OUT / out.name / "questions.parquet"  # written by --scan, always under OUT
    n_all = pq.ParquetFile(path).metadata.num_rows
    companies = load_companies()
    system = system_prompt(companies)
    prepare_out(out)
    failed_path = out / "failed.parquet"
    failed = pd.read_parquet(failed_path) if failed_path.exists() else pd.DataFrame(columns=["article_id", "error"])
    size = cfg["chunk_size"]
    if limit or retry:  # a small set: pick its ids from one column, then read only those rows
        ids = pd.read_parquet(path, columns=["article_id"])["article_id"]
        ids = ids.sample(n=min(limit, len(ids)), random_state=cfg["seed"]) if limit else ids[ids.isin(failed["article_id"])]
        todo = pd.read_parquet(path, filters=[("article_id", "in", list(ids))]).sort_values("article_id").reset_index(drop=True)
        k0 = len(list(out.glob("retry-*.parquet"))) if retry else 0
        pre = "retry" if retry else "part"
        chunks = ((f"{pre}-{k0 + i:05d}", todo.iloc[j:j + size]) for i, j in enumerate(range(0, len(todo), size)))
        n_total = len(todo)
    else:  # the full run: one chunk in memory at a time; a chunk already written is skipped
        done_k = {int(p.stem.split("-")[1]) for p in out.glob("part-*.parquet")}
        batches = pq.ParquetFile(path).iter_batches(batch_size=size)
        chunks = ((f"part-{i:05d}", b.to_pandas()) for i, b in enumerate(batches) if i not in done_k)
        n_total = n_all - min(len(done_k) * size, n_all)
    if not n_total:
        print("nothing to do")
        return
    print(f"{n_total} articles to ask", flush=True)

    tok = AutoTokenizer.from_pretrained(cfg["model"])
    sys_tokens = len(tok(system, add_special_tokens=False)["input_ids"])
    params = SamplingParams(temperature=cfg["temperature"], seed=cfg["seed"], max_tokens=cfg["max_output_tokens"],
                            structured_outputs=StructuredOutputsParams(json=schema(companies)))
    llm = LLM(model=cfg["model"], enable_prefix_caching=True, seed=cfg["seed"],  # the shared system prompt is cached
              max_model_len=sys_tokens + cfg["max_input_tokens"] + cfg["max_output_tokens"] + 64)
    logf = open(Path("logs") / f"{out.parent.name}_{out.name}.log", "a")
    t_start, n_done, tok_in, tok_out, longest, all_failed = time.time(), 0, 0, 0, 0.0, 0
    for name, chunk in chunks:
        if stop_after and time.time() - T_PROC + 2 * longest > stop_after:  # stop between chunks, never inside one
            print(f"stopping before the time limit at {name}; the next run resumes here", flush=True)
            break
        t0 = time.time()
        convs, cut = [], []
        for q in chunk.to_dict("records"):
            msg, c = fit_message(json.loads(q["hits"]), q["headline"], q["text"], tok, cfg["max_input_tokens"])
            convs.append([{"role": "system", "content": system}, {"role": "user", "content": msg}])
            cut.append(c or q["was_cut"])
        rows, errs, c_in, c_out = [], [], 0, 0
        try:
            res = llm.chat(convs, params, chat_template_kwargs={"enable_thinking": False}, use_tqdm=False)
        except Exception as e:  # generation error: the whole chunk is retried with --retry
            res = []
            errs = [{"article_id": a, "error": f"generation: {type(e).__name__}: {e}"[:300]} for a in chunk["article_id"]]
        for j, o in enumerate(res):
            a = chunk["article_id"].iloc[j]
            c_in += len(o.prompt_token_ids)
            c_out += len(o.outputs[0].token_ids)
            try:
                if o.outputs[0].finish_reason == "length":
                    raise ValueError("output_truncated")
                ans = parse_answer(o.outputs[0].text, companies)
            except ValueError as e:
                errs.append({"article_id": a, "error": str(e)[:300]})
                continue
            rows.append({"article_id": a, "companies": ans, "cut": cut[j],
                         "model": cfg["model"], "prompt_version": str(cfg["prompt_version"])})
        if rows:
            write_parquet(pd.DataFrame(rows), out / f"{name}.parquet")
        done = {r["article_id"] for r in rows}
        failed = pd.concat([failed[~failed["article_id"].isin(done)], pd.DataFrame(errs, columns=["article_id", "error"])],
                           ignore_index=True).drop_duplicates("article_id", keep="last")
        write_parquet(failed, failed_path)

        n_done += len(chunk)
        longest = max(longest, time.time() - t0)
        tok_in += c_in
        tok_out += c_out
        rate = n_done / (time.time() - t_start)
        line = json.dumps({
            "chunk": name, "done": n_done, "remaining": n_total - n_done, "articles_per_s": round(rate, 2),
            "eta_min": round((n_total - n_done) / rate / 60, 1), "input_tokens": c_in, "output_tokens": c_out,
            "gpu_gb": gpu_used_gb(),
            "some_company_share": round(sum(bool(r["companies"]) for r in rows) / len(rows), 3) if rows else None,
            "cut": sum(r["cut"] for r in rows), "failed": len(errs), "chunk_s": round(time.time() - t0, 1),
        })
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()
        all_failed = all_failed + 1 if not rows else 0
        if all_failed == 3:  # something systematic (prompt, schema, model): stop instead of burning GPU time
            sys.exit(f"3 chunks in a row with no valid answer; last error: {errs[-1]['error'] if errs else '?'}")

    if limit:
        secs = time.time() - t_start
        print(f"\nfull run (excludes model load): {secs / n_done * n_all / 3600:.1f} h at this rate for {n_all} articles, "
              f"total input tokens {tok_in}, output tokens {tok_out}, failed articles {len(failed)}")


def build(out: Path) -> None:
    yes = read_answers(out).explode("companies").dropna(subset=["companies"]).rename(columns={"companies": "company_id"})
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
    ap.add_argument("--stop-after", type=float, default=None, help="seconds since start; no new chunk after that")
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
    run(cfg, (OUT_TEST if args.limit else OUT) / pv, args.limit, args.retry, args.stop_after)


if __name__ == "__main__":
    main()
