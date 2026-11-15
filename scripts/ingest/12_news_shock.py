"""Steps 43 to 44 and 61 to 69: the news shock u(k,D) = E(k,D) - S(k,D) beta_hat.

    uv run python scripts/ingest/12_news_shock.py [--freeze 2026-08-27]

Inputs: embeddings/articles/part-*.{npy,parquet} (07), matches.parquet and articles.parquet (08),
characteristics.parquet (11). Output: data/news/news_shocks.parquet, one row per company-day with
an article, a row S and a beta: company_id, day, u, E, Sbeta (each a float32 vector of 2,560), S
(28 float32: constant, beta, me, bm, prof, inv, mom_s, vol_s, ill_s, mom_pm, vol_pm, ill_pm, 16
industry dummies), u_frozen, and the combined metric (step 58): w_mom, w_vol, w_ill, comb_mom,
comb_vol, comb_ill.

E: day-mean embedding (43), each coordinate standardized with the mean and sd over company-days
strictly before that day (44). S: each day's cross-section ranked to [-1,1], ties averaged, missing
0 (61); momentum, volatility and illiquidity each have a stock column and a Polymarket column, no
blend (58, 62). beta for day D is least squares on company-days dated in the calendar month ending
D-1; a column with no non-missing value in those rows (an industry, or a Polymarket version) is
dropped from that day's equation (63-67). Combined metric (58): after beta is solved,
w = |beta PM row| / (|beta stock row| + |beta PM row|) (Euclidean length of the 2,560 slopes; 0 for
a dropped column, w = 0 if both are) and comb = (1-w) stock rank + w PM rank. u_frozen uses the beta
built for the day after --freeze (69). Everything is dated D-1 or earlier except E(k,D) itself.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

NEWS = Path("data/news")
CHARS = ["beta", "me", "bm", "prof", "inv", "mom_s", "vol_s", "ill_s", "mom_pm", "vol_pm", "ill_pm"]
PAIRS = ["mom", "vol", "ill"]  # stock column {k}_s and Polymarket column {k}_pm (step 58)


def rank_x(df: pd.DataFrame, col: str) -> pd.Series:
    """Step 61: rank r of n on one day -> 2(r-1)/(n-1) - 1; ties average; missing stays NaN."""
    g = df.groupby("day")[col]
    r, n = g.rank(method="average"), g.transform("count")
    return (2 * (r - 1) / (n - 1).where(n > 1) - 1).where(n > 1, 0.0).where(df[col].notna())


def build_s(ch: pd.DataFrame) -> pd.DataFrame:
    out = ch[["company_id", "day"]].copy()
    out["const"] = 1.0
    for c in CHARS:
        out[c] = rank_x(ch, c).fillna(0.0)
    inds = sorted(ch["industry"].dropna().unique())[:-1]  # 17 groups -> 16 dummies, last is the base
    for i in inds:
        out[f"ind_{i}"] = (ch["industry"] == i).astype(float)
    return out


def day_means(m: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Step 43: mean embedding per (company, day); an article matched to two companies counts for both."""
    keys = m[["company_id", "day"]].drop_duplicates().sort_values(["day", "company_id"]).reset_index(drop=True)
    m = m.merge(keys.reset_index(names="gid"), on=["company_id", "day"])
    cnt = np.zeros(len(keys))
    sums = None
    for p in sorted((NEWS / "embeddings/articles").glob("part-*.parquet")):
        ids = pd.read_parquet(p)["article_id"]
        sub = m[m["article_id"].isin(ids)]
        if sub.empty:
            continue
        v = np.load(p.with_suffix(".npy"), mmap_mode="r")
        if sums is None:
            sums = np.zeros((len(keys), v.shape[1]), np.float32)
        row = pd.Index(ids).get_indexer(sub["article_id"])
        o = np.argsort(sub["gid"].to_numpy(), kind="stable")
        g, row = sub["gid"].to_numpy()[o], row[o]
        st = np.flatnonzero(np.r_[True, g[1:] != g[:-1]])
        sums[g[st]] += np.add.reduceat(np.asarray(v[row]), st, axis=0)
        cnt += np.bincount(g, minlength=len(keys))
    got = cnt > 0
    print(f"{int(got.sum())} of {len(keys)} company-days have an embedded article")
    sums /= np.maximum(cnt, 1)[:, None].astype(np.float32)
    return keys.assign(n_art=cnt.astype(int)), sums


def standardize(keys: pd.DataFrame, X: np.ndarray) -> np.ndarray:
    """Step 44: sd/mean over company-days strictly before each day. Days with < 2 earlier rows are NaN."""
    E = np.full(X.shape, np.nan, np.float32)
    s1, s2, n = np.zeros(X.shape[1]), np.zeros(X.shape[1]), 0
    for _, ix in keys.groupby("day").indices.items():
        x = X[ix].astype(np.float64)
        if n >= 2:
            mu = s1 / n
            sd = np.sqrt(np.maximum((s2 - n * mu**2) / (n - 1), 0))
            E[ix] = np.where(sd > 1e-8, (x - mu) / np.where(sd > 1e-8, sd, 1), 0)
        s1 += x.sum(0)
        s2 += (x**2).sum(0)
        n += len(ix)
    return E


def fit(S, E, day, ok, D):
    """Steps 65-66: rows dated in the calendar month ending D-1; returns (kept columns, beta) or None."""
    end = D - pd.Timedelta(days=1)
    start = end - pd.DateOffset(months=1) + pd.Timedelta(days=1)
    w = ok & (day >= start) & (day <= end)
    keep = np.flatnonzero((np.arange(S.shape[1]) < 1) | S[w].any(0))  # a column with nothing but missing goes
    if w.sum() < len(keep):
        return None
    return keep, np.linalg.lstsq(S[w][:, keep].astype(np.float64), E[w].astype(np.float64), rcond=None)[0]


def combined(Sm, ix, cols, keep, b):
    """Step 58: per pair, w from the lengths of the slope rows, and (1-w) stock rank + w PM rank."""
    length = dict(zip(keep, np.linalg.norm(b, axis=1)))  # a dropped column has length 0
    w, comb = np.zeros(3), np.zeros((len(ix), 3), np.float32)
    for n, k in enumerate(PAIRS):
        i, j = cols.index(f"{k}_s"), cols.index(f"{k}_pm")
        ls, lp = length.get(i, 0.0), length.get(j, 0.0)
        w[n] = lp / (ls + lp) if ls + lp > 0 else 0.0
        comb[:, n] = (1 - w[n]) * Sm[ix, i] + w[n] * Sm[ix, j]
    return w, comb


def lists(a: np.ndarray) -> pa.Array:
    return pa.FixedSizeListArray.from_arrays(pa.array(a.astype(np.float32).ravel()), a.shape[1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", default="2026-08-27", help="last train day; step 69 beta is the one built for the next day")
    args = ap.parse_args()

    ch = pd.read_parquet(NEWS / "characteristics.parquet")
    ch["day"] = pd.to_datetime(ch["day"])
    S = build_s(ch)
    cols = [c for c in S.columns if c not in ("company_id", "day")]

    art = pd.read_parquet(NEWS / "articles.parquet", columns=["article_id", "day"])
    m = pd.read_parquet(NEWS / "matches.parquet", columns=["article_id", "company_id"]).merge(art, on="article_id")
    m["day"] = pd.to_datetime(m["day"])
    keys, X = day_means(m)
    E = standardize(keys, X)
    del X
    keys = keys.merge(S, on=["company_id", "day"], how="left")
    ok = np.isfinite(E[:, 0]) & keys["const"].notna().to_numpy()  # needs E (earlier days exist) and a row S
    Sm = keys[cols].fillna(0.0).to_numpy(np.float32)
    day = keys["day"].to_numpy()

    u, Sb = np.full(E.shape, np.nan, np.float32), np.full(E.shape, np.nan, np.float32)
    wv, cv = np.full((len(keys), 3), np.nan, np.float32), np.full((len(keys), 3), np.nan, np.float32)
    first = keys.loc[keys["const"].notna(), "day"].min()  # first article day with a characteristics row
    frozen = fit(Sm, E, day, ok, pd.Timestamp(args.freeze) + pd.Timedelta(days=1))
    for D, ix in keys.groupby("day").indices.items():
        D = pd.Timestamp(D)
        ix = ix[ok[ix]]
        if D - pd.Timedelta(days=1) - pd.DateOffset(months=1) < first:  # steps 65, 68: a full month of articles first
            continue
        f = fit(Sm, E, day, ok, D)
        if f is None:
            continue
        keep, b = f
        Sb[ix] = Sm[ix][:, keep] @ b
        u[ix] = E[ix] - Sb[ix]
        w3, cv[ix] = combined(Sm, ix, cols, keep, b)
        wv[ix] = w3
    if frozen is None:
        raise SystemExit(f"no beta for {args.freeze} + 1 day: step 69 cannot be built")
    uf = np.full(E.shape, np.nan, np.float32)
    uf[ok] = E[ok] - Sm[ok][:, frozen[0]] @ frozen[1]

    keep = np.isfinite(u[:, 0])
    t = pa.table({"company_id": keys["company_id"][keep].to_numpy(), "day": keys["day"][keep].to_numpy(),
                  "u": lists(u[keep]), "E": lists(E[keep]), "Sbeta": lists(Sb[keep]),
                  "S": lists(Sm[keep]), "u_frozen": lists(uf[keep]),
                  **{f"w_{k}": wv[keep, n] for n, k in enumerate(PAIRS)},
                  **{f"comb_{k}": cv[keep, n] for n, k in enumerate(PAIRS)}})
    pq.write_table(t, NEWS / "news_shocks.parquet")
    print(f"{int(keep.sum())} company-days with a shock -> {NEWS / 'news_shocks.parquet'}; S columns: {cols}")


if __name__ == "__main__":
    main()
