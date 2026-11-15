"""Steps 15 and 16: find candidate articles in GDELT's GKG from its free public files.

One unit of work is one calendar month. The month's GKG 2.1 files (one zip per 15 minutes,
listed in masterfilelist.txt) are downloaded one at a time into memory, filtered, and
discarded; no raw file touches disk. A record is kept when a company name from
config/companies.yaml appears as a whole word with exact capitalization in the record's
`V2Organizations` or `AllNames` field. V2Organizations is matched too because its capitalization
is verified and AllNames' is not; each row records which field matched. Tickers are never used.

Output: one row per (URL, company). In the training period a month keeps a deterministic sample
of up to `sample_per_company_month` URLs per company, ranked by a hash of the record id after
the whole month is scanned. GDELT dates articles to the day (timestamp_precision = "day").
"""
from __future__ import annotations

import hashlib
import io
import re
import time
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import httpx
import pandas as pd

MASTER_LIST = "https://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
N_COLS = 27
# GKG 2.1 column positions (0-based). Position 0, 1 and 4 are checked against the data in parse_file.
C_ID, C_DATE, C_COLLECTION, C_SOURCE, C_URL, C_ORGS, C_ALLNAMES = 0, 1, 2, 3, 4, 14, 23
OUT_COLUMNS = ["GKGRECORDID", "day", "url", "source", "company_id", "matched_name", "matched_field"]

_WORD = re.compile(r"\w+", re.ASCII)  # ASCII like RE2's \b, which BigQuery used


class SchemaError(RuntimeError):
    """A GKG file does not look like GKG 2.1; stop the run rather than filter garbage."""


def whole_word_pattern(name: str) -> str:
    """Regex: the exact name between word boundaries. "Apple" matches "Apple's", not "Applebee"."""
    special = set(r"\.^$|?*+()[]{}")
    # either apostrophe: AllNames may spell "McDonald's" with a straight or a curly one
    body = "".join("['\u2019]" if ch in "'\u2019" else "\\" + ch if ch in special else ch for ch in name)
    return r"\b" + body + r"\b"


def record_hash(record_id: str) -> int:
    """Stable sample rank. BigQuery's FARM_FINGERPRINT is not available outside BigQuery, so
    this is a SHA-1 prefix; the sample differs from a BigQuery draw but is the same on every rerun."""
    return int.from_bytes(hashlib.sha1(record_id.encode()).digest()[:8], "big")


class NameIndex:
    """Every (company, name) pair, indexed by the name's first word.

    A name can only match where its first word is a whole token of the text (the name starts
    at a word boundary, and the word it starts with ends at the first non-word character the
    name itself contains). So a row costs one tokenisation, then a regex per name whose first
    word occurs in the row, never one regex per name. Names that do not start with a word
    character are checked on every row.
    """

    def __init__(self, names: dict[str, tuple[str, ...]]):
        self.by_token: dict[str, list[tuple[str, str, re.Pattern]]] = defaultdict(list)
        self.always: list[tuple[str, str, re.Pattern]] = []
        for cid, ns in names.items():
            for n in ns:
                entry = (cid, n, re.compile(whole_word_pattern(n), re.ASCII))
                m = _WORD.match(n)
                (self.by_token[m.group()] if m else self.always).append(entry)

    def matches(self, text: str) -> set[tuple[str, str]]:
        if not text:
            return set()
        out = {(c, n) for c, n, rx in self.always if rx.search(text)}
        for tok in set(_WORD.findall(text)):
            for c, n, rx in self.by_token.get(tok, ()):
                if rx.search(text):
                    out.add((c, n))
        return out


def parse_file(text: str, index: NameIndex, spans: dict[str, list[tuple[date, date]]],
               days: set[str], label: str) -> tuple[dict, int]:
    """Filter one decoded GKG file. Returns ({(url, company): (record_id, name, field, day, source)}, rows).

    Raises SchemaError when most rows do not have 27 columns or do not look like GKG 2.1.
    """
    hits: dict[tuple[str, str], tuple] = {}
    rows = good = shaped = 0
    for line in text.split("\n"):
        if not line:
            continue
        rows += 1
        c = line.split("\t")
        if len(c) != N_COLS:
            continue
        good += 1
        if len(c[C_DATE]) == 14 and c[C_DATE].isdigit() and c[C_URL].startswith("http"):
            shaped += 1
        if c[C_COLLECTION] != "1" or c[C_DATE][:8] not in days:  # collection 1 = web news, as in the BigQuery query
            continue
        day = date(int(c[C_DATE][:4]), int(c[C_DATE][4:6]), int(c[C_DATE][6:8]))
        in_orgs = index.matches(c[C_ORGS])
        in_all = index.matches(c[C_ALLNAMES])
        for cid, name in in_orgs | in_all:
            if not any(a <= day <= b for a, b in spans.get(cid, ())):
                continue
            field = "both" if (cid, name) in in_orgs and (cid, name) in in_all else (
                "V2Organizations" if (cid, name) in in_orgs else "AllNames")
            key = (c[C_URL], cid)
            cand = (c[C_ID], name, field, day, c[C_SOURCE])
            if key not in hits or cand[:2] < hits[key][:2]:
                hits[key] = cand
    if rows and (good < 0.5 * rows or shaped < 0.5 * good):
        raise SchemaError(f"{label}: {good}/{rows} rows have {N_COLS} columns and {shaped} of those have a "
                          f"14-digit DATE in column {C_DATE} and an http URL in column {C_URL}")
    return hits, rows


def _get(client: httpx.Client, url: str, retries: int = 4) -> bytes | None:
    """Body of `url`, or None on 404. Retries transient errors, then raises."""
    for attempt in range(retries + 1):
        try:
            r = client.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            if attempt == retries or (isinstance(e, httpx.HTTPStatusError)
                                      and e.response.status_code < 500 and e.response.status_code != 429):
                raise
            time.sleep(2 ** attempt * 2)
    raise AssertionError  # unreachable


def month_files(client: httpx.Client, month: str) -> list[str]:
    """GKG zip URLs of `month` ('YYYY-MM') from masterfilelist.txt, in time order."""
    prefix, urls = month.replace("-", ""), []
    for attempt in range(4):
        urls.clear()
        try:
            with client.stream("GET", MASTER_LIST) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    f = line.split()
                    if len(f) != 3:  # the index has a few truncated lines; an empty month still raises below
                        continue
                    if f[2].endswith(".gkg.csv.zip") and f[2].rsplit("/", 1)[-1].startswith(prefix):
                        urls.append(f[2])
            break
        except (httpx.TransportError, httpx.HTTPStatusError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt * 5)
    if not urls:
        raise SchemaError(f"no GKG files for {month} in {MASTER_LIST}")
    return sorted(set(urls))


def _one_file(client: httpx.Client, url: str, index: NameIndex, spans, days):
    """('ok', hits, rows) | ('missing', url) | ('failed', url, reason); SchemaError propagates."""
    last = ""
    for attempt in range(3):  # a truncated download looks like a bad zip, so re-download too
        try:
            data = _get(client, url)
            if data is None:
                return ("missing", url)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
                if len(names) != 1:
                    raise SchemaError(f"{url}: zip holds {len(names)} files")
                text = z.read(names[0]).decode("utf-8", errors="replace")
            hits, rows = parse_file(text, index, spans, days, url)
            return ("ok", hits, rows)
        except (httpx.HTTPError, zipfile.BadZipFile, EOFError, OSError) as e:
            last = f"{type(e).__name__}: {e}".replace("\n", " ")
            time.sleep(2 ** attempt * 2)
    return ("failed", url, last)


def pull_month(month: str, ranges: pd.DataFrame, names: dict[str, tuple[str, ...]], sample: int | None,
               workers: int = 4, contact: str = "", only_days: tuple[int, ...] | None = None) -> tuple[pd.DataFrame, dict, list[str], list[str]]:
    """Scan one month. `ranges`: company_id, range_start, range_end, all inside that month.

    `only_days`: days of the month to scan (training period); None scans every day in `ranges`.
    Files are chosen by day from the file list before anything is downloaded.

    Returns (candidates, stats, missing_urls, failed_lines).
    """
    spans: dict[str, list[tuple[date, date]]] = defaultdict(list)
    for r in ranges.itertuples():
        spans[r.company_id].append((r.range_start, r.range_end))
    days = {d.strftime("%Y%m%d") for v in spans.values() for a, b in v for d in pd.date_range(a, b)
            if only_days is None or d.day in only_days}
    index = NameIndex({c: names[c] for c in spans})
    headers = {"User-Agent": f"thesis-polymarket-ingest ({contact})" if contact else "thesis-polymarket-ingest"}

    hits: dict[tuple[str, str], tuple] = {}
    rows, missing, failed = 0, [], []
    with httpx.Client(headers=headers, timeout=60, follow_redirects=True,
                      limits=httpx.Limits(max_connections=workers)) as client:
        files = month_files(client, month)
        # file timestamps name the day their records carry, so files on days nobody needs are skipped
        todo = [u for u in files if u.rsplit("/", 1)[-1][:8] in days]
        with ThreadPoolExecutor(workers) as ex:
            for res in ex.map(lambda u: _one_file(client, u, index, spans, days), todo):
                if res[0] == "ok":
                    rows += res[2]
                    for k, v in res[1].items():  # files arrive in time order, so the first record id wins ties
                        if k not in hits or v[:2] < hits[k][:2]:
                            hits[k] = v
                elif res[0] == "missing":
                    missing.append(res[1])
                else:
                    failed.append(f"{res[1]}\t{res[2]}")

    df = pd.DataFrame([(v[0], v[3], k[0], v[4], k[1], v[1], v[2]) for k, v in hits.items()], columns=OUT_COLUMNS)
    if sample and len(df):
        df["_h"] = df["GKGRECORDID"].map(record_hash)
        df = (df.sort_values(["company_id", "_h", "GKGRECORDID"]).groupby("company_id").head(sample)
              .drop(columns="_h"))
    df = df.sort_values(["company_id", "GKGRECORDID"]).reset_index(drop=True)
    stats = {"files_listed": len(files), "files_needed": len(todo), "files_missing": len(missing),
             "files_failed": len(failed), "rows_scanned": rows, "candidate_rows": len(df)}
    return df, stats, missing, failed


def write_month(df: pd.DataFrame, out_dir: str, period: str, month: str) -> Path:
    p = Path(out_dir) / f"period={period}" / f"month={month}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")  # write beside the target, then rename: a stopped run leaves no partial month
    df.assign(timestamp_precision="day").to_parquet(tmp, index=False)
    tmp.replace(p)
    return p


def load_candidates(out_dir: str) -> pd.DataFrame:
    parts = sorted(Path(out_dir).glob("period=*/month=*.parquet"))
    if not parts:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(p).assign(period=p.parent.name.split("=", 1)[1]) for p in parts],
                   ignore_index=True)
    return df.drop_duplicates(["company_id", "url"]).reset_index(drop=True)
