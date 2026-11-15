"""Steps 17 and 18: download article text and recheck the company name as each chunk finishes.

Each URL is fetched once (async httpx, trafilatura extraction; measured at 11.4 articles/s
with 77.8% success). `run` handles one hash part of the URLs (`--part i --parts n`), so n
tasks fetch in parallel. Shards `<out_dir>/part-t<i>-*.parquet` hold one row per URL. Every row has
url and status. Only an article whose extracted text names one of its candidate companies also has
headline, lede, body, source, day, period and the matched names; failures and the rest keep no text.
A stopped run resumes where it ended (non-200 rows other than 403/404/410 and the parse codes below
are retried into a later shard, which wins). Same-headline duplicates are removed after mapping (08_map_companies.py --build).

Name rule (steps 16 and 17): a company name as a whole word with exact capitalization.
"""
from __future__ import annotations

import asyncio
import collections
import hashlib
import json
import multiprocessing
import os
import re
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

import pandas as pd

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


# ── text helpers ────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Same-URL key: lowercase scheme and host; no fragment, trailing slash or utm_*/fbclid/gclid parameters."""
    u = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                       if not (k.lower().startswith("utm_") or k.lower() in ("fbclid", "gclid"))])
    return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip("/"), query, ""))


def article_id(url: str) -> str:
    """sha256 of the normalized URL. Equal to the old sha256(url) for every URL that normalization leaves unchanged."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()


def names_found(names, text: str | None) -> list[str]:
    """Names that appear in `text` as whole words with exact capitalization."""
    if not text:
        return []
    text = text.replace("\u2019", "'")  # curly apostrophe: "McDonald\u2019s" is "McDonald's"
    return [n for n in names if re.search(r"\b" + re.escape(n.replace("\u2019", "'")) + r"\b", text)]


def split_lede(body: str) -> tuple[str, str]:
    """(first paragraph, remaining paragraphs) of the extracted text."""
    paras = [p.strip() for p in body.split("\n") if p.strip()]
    return (paras[0], "\n".join(paras[1:])) if paras else ("", "")


def embedding_text(headline, lede, body, source, day) -> str:
    """Step 21: headline, lede, body, source and date in one text."""
    return f"{headline or ''}\n\n{lede}\n\n{body}\n\nSource: {source or ''}. Date: {day}."


def normalize_headline(t: str | None) -> str:
    return re.sub(r"[^\w]+", " ", (t or "").lower()).strip()


# ── fetching ────────────────────────────────────────────────────────────────

# Final statuses for pages the parser could not handle; resume never retries them.
PARSE_CRASH, PARSE_TIMEOUT, TOO_LARGE = -2, -3, -4
FINAL_STATUS = {PARSE_CRASH: "parse_crash", PARSE_TIMEOUT: "parse_timeout", TOO_LARGE: "html_too_large"}


def _extract(html: str):
    """Runs in a worker process: a native crash in lxml/trafilatura kills only that worker."""
    import trafilatura  # lazy: the mapping env imports this module without it
    body = trafilatura.extract(html, favor_recall=False)
    meta = trafilatura.extract_metadata(html)
    return body or "", meta.title if meta else None


class ParsePool:
    """`workers` single-process executors, one page each at a time, so a crash or hang is
    attributed to exactly one URL. The broken or hung executor is replaced."""

    def __init__(self, workers: int, timeout_s: float):
        self.timeout_s = timeout_s
        self.slots: asyncio.Queue = asyncio.Queue()
        for _ in range(workers):
            self.slots.put_nowait(self._new())

    @staticmethod
    def _new() -> ProcessPoolExecutor:  # spawn, not fork: the parent runs threads and an event loop
        return ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))

    @staticmethod
    def _discard(ex: ProcessPoolExecutor) -> None:
        for proc in list((getattr(ex, "_processes", None) or {}).values()):
            proc.kill()
        ex.shutdown(wait=False, cancel_futures=True)

    async def parse(self, html: str):
        """-> (body, title) or the final status PARSE_CRASH / PARSE_TIMEOUT."""
        ex = await self.slots.get()
        try:
            return await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(ex, _extract, html),
                                          self.timeout_s)
        except asyncio.TimeoutError:
            self._discard(ex)
            ex, status = self._new(), PARSE_TIMEOUT
        except BrokenProcessPool:
            self._discard(ex)
            ex, status = self._new(), PARSE_CRASH
        finally:
            self.slots.put_nowait(ex)
        return status

    def close(self) -> None:
        while not self.slots.empty():
            self.slots.get_nowait().shutdown(wait=True)


async def _fetch_one(client, url, glob, dom, pool, max_html_bytes):
    t0 = time.time()
    rec = {"url": url, "status": None, "final_url": None, "error_type": None,
           "page_title": None, "body": None}
    async with dom[urlparse(url).netloc], glob:  # domain first, so waiting on a busy domain holds no global slot
        try:
            resp = await client.get(url)
            rec.update(status=resp.status_code, final_url=str(resp.url))
            if resp.status_code == 200:
                if len(resp.content) > max_html_bytes:
                    rec.update(status=TOO_LARGE)
                else:
                    out = await pool.parse(resp.text)
                    if isinstance(out, int):
                        rec.update(status=out)
                    else:
                        rec.update(body=out[0], page_title=out[1])
        except Exception as e:  # network and decoding errors are recorded per URL
            rec.update(status=-1, error_type=type(e).__name__)
    rec["secs"] = time.time() - t0
    return rec


async def fetch_urls(urls, *, contact="", global_concurrency=24, per_domain_concurrency=2,
                     timeout_s=20, parse_workers=3, parse_timeout_s=30, max_html_bytes=5_000_000) -> list[dict]:
    import httpx
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if contact:
        headers["From"] = contact
    glob = asyncio.Semaphore(global_concurrency)
    dom = collections.defaultdict(lambda: asyncio.Semaphore(per_domain_concurrency))
    pool = ParsePool(parse_workers, parse_timeout_s)
    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout_s, follow_redirects=True,
                                     limits=httpx.Limits(max_connections=global_concurrency * 2)) as c:
            return await asyncio.gather(*[_fetch_one(c, u, glob, dom, pool, max_html_bytes) for u in urls])
    finally:
        pool.close()


COLS = ["url", "status", "headline", "lede", "body", "source", "day", "period", "names"]
WATCH = ("Instagram", "Facebook")  # names reported per chunk: likely page boilerplate


def judge(rec: dict, info: tuple, names: dict) -> tuple[dict, str | None, list[str]]:
    """Name recheck on the extracted text. -> (shard row, dropped reason or None, matched names).
    info = (candidate company ids, period, day, source)."""
    row = {"url": rec["url"], "status": rec["status"]}
    if rec["status"] != 200:
        return row, FINAL_STATUS.get(rec["status"], "fetch_failed"), []
    if not rec["body"]:
        return row, "empty_body", []
    ids, period, day, source = info
    text = f"{rec['page_title'] or ''}\n{rec['body']}"
    found = list(dict.fromkeys(n for c in ids for n in names_found(names[c], text)))
    if not found:
        return row, "name_missing", []
    lede, body = split_lede(rec["body"])
    row.update(headline=rec["page_title"], lede=lede, body=body, source=source, day=day,
               period=period, names=found)
    return row, None, found


def write_shard(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")  # *.tmp does not match part-*.parquet, so readers never see it
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def run(cands: pd.DataFrame, names: dict, out_dir: str, *, contact="", global_concurrency=24,
        per_domain_concurrency=1, timeout_s=20, chunk_size=500, part=0, parts=1, limit=None,
        parse_workers=3, parse_timeout_s=30, max_html_bytes=5_000_000) -> int:
    """Fetch this part's URLs not yet in out_dir, one shard per chunk. Returns the number fetched."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mine = f"part-t{part}-"
    shards = sorted(out.glob("part-*.parquet"))
    done = set()
    if shards:
        prev = pd.concat([pd.read_parquet(p, columns=["url", "status"]) for p in shards])
        # transient failures (timeouts, 429, 5xx, network errors) are retried; 403/404/410 and the
        # parse codes (crash, timeout, oversized) are final, so a resume cannot loop on a bad page
        # compared on the normalized URL, so shards written under the raw URL still count as done
        done = {normalize_url(u) for u in prev.loc[prev["status"].isin([200, 403, 404, 410, *FINAL_STATUS]), "url"]}
    cands = cands.assign(key=cands["url"].map(normalize_url))
    first = cands.drop_duplicates("key").set_index("key")[["period", "day", "source"]]
    ids = cands.groupby("key", sort=False)["company_id"].agg(list)
    raw = cands.drop_duplicates("key").set_index("key")["url"]  # the first spelling is the one fetched

    def in_part(k):  # a task may now own a URL an old shard holds, but `done` is read from all shards
        return int(hashlib.sha256(k.encode()).hexdigest()[:8], 16) % parts == part

    todo = [raw[k] for k in dict.fromkeys(cands["key"]) if in_part(k) and k not in done][:limit]
    own = [int(p.stem.split("-")[2]) for p in shards if p.name.startswith(mine)]
    n = max(own) + 1 if own else 0  # never reuse a shard number
    for i in range(0, len(todo), chunk_size):
        urls = todo[i:i + chunk_size]
        t0 = time.time()
        fetched = asyncio.run(fetch_urls(urls, contact=contact, global_concurrency=global_concurrency,
                                         per_domain_concurrency=per_domain_concurrency, timeout_s=timeout_s,
                                         parse_workers=parse_workers, parse_timeout_s=parse_timeout_s,
                                         max_html_bytes=max_html_bytes))
        rows, dropped = [], collections.Counter()
        by_name = {w: {"kept": 0, "only": 0} for w in WATCH}
        for rec in fetched:
            key = normalize_url(rec["url"])
            row, reason, found = judge(rec, (ids[key], *first.loc[key]), names)
            rows.append(row)
            if reason:
                dropped[reason] += 1
            for w in WATCH:
                if w in found:
                    by_name[w]["kept"] += 1
                    by_name[w]["only"] += found == [w]
        write_shard(pd.DataFrame(rows, columns=COLS), out / f"part-t{part}-{n:05d}.parquet")
        n += 1
        failed = dropped.pop("fetch_failed", 0)
        parse = {k: dropped.pop(k, 0) for k in FINAL_STATUS.values()}
        print(json.dumps({"part": part, "chunk": n - 1, "fetched": len(urls), "failed": failed, **parse,
                          "kept": len(urls) - failed - sum(parse.values()) - sum(dropped.values()),
                          "dropped": dict(dropped),
                          "by_name": by_name, "chunk_s": round(time.time() - t0, 1),
                          "remaining": len(todo) - i - len(urls)}), flush=True)
    return len(todo)
