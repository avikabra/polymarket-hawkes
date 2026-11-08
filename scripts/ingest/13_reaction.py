"""Steps 74 to 78: the Polymarket reaction y(k,D) and the stock reaction y^S(k,D).

    uv run python scripts/ingest/13_reaction.py

Reads data/polymarket/contracts/markets.parquet, the trades (03), data/stocks/prices.parquet.
Output data/news/reactions.parquet, one row per company-day with at least one qualifying contract:
  y          dollar-weighted mean of sign * (log-odds(last trade < M+24h) - log-odds(last trade < M)),
             weights = each contract's dollars traded on D itself (steps 76-77); null if all are 0
  y_money    same weights, mean of (p' - p) / p with p the good-news-side price (step 77)
  y_stock    adj_close of the next day / adj_close of the last day <= D, minus 1; only when D+1 trades
  dv_pm_24h, flow_small, flow_large   24h dollars, and net good-news-side flow (buys - sells) in
             trades under / at least $1,000 (steps 104-105)
  y_big, y_money_big   y and y_money over contracts with >= $10,000 traded before M (step 96)
  y_type_<contract_type>   y over the company's contracts of that type (null if none that day)
  y_ladder   log-price reaction of the company's ladders (steps 76a-76f), weights = ladder dollars on D;
             null if no ladder fits at both times. dlog_s: the same average of the change in ln s.
Also data/news/ladder_reactions.parquet, one row per ladder-day: company_id, day, event_id, direction
(close | up | down), n_rungs, mu0, mu1, s0, s1, dmu, dlog_s, weight.
M is midnight Eastern after D; the window is [M, M + 24h). A contract counts when it is not a
closing bucket, has a single direction, is open at M (start <= M < actual end), has >= $1,000 traded
before M, and has a trade in the window. Weights are each contract's dollars traded on D, the
Eastern calendar day before M (known at M); a contract with none on D has weight 0.
Ladder (76a-76e): the counted rungs of one close_ladder event, or of one barrier_ladder event with the
same direction (above = up, below = down). Close-ladder "below" rungs use l -> -l. At M and M + 24h fit
l = c + m ln K by least squares weighted by each rung's dollars traded up to that time; b = -m (close, up)
or m (down) must be > 0, then mu = -c / m and s = 1 / b. Same rungs at both times, at least 2.
sign = +1 when YES pays if the stock rises or the contract has no direction (earnings, up/down,
"above"), -1 for "below". Buying the good-news side = YES_BUY when sign = +1, YES_SELL when -1
(side is already in YES terms, 03). Log-odds only; price_raw is clipped to (0.001, 0.999).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ET = "America/New_York"
DAY = 86400
FLOOR = 1000.0
BIG = 10000.0


LADDERS = ["close_ladder", "barrier_ladder"]


def ladder_fit(x: np.ndarray, l: np.ndarray, w: np.ndarray, down: bool):
    """Step 76d: weighted line l = c + m x, x = ln K. Returns (mu, s) or None when b <= 0."""
    if np.ptp(x) < 1e-9:  # every rung at one strike: no line
        return None
    xm, lm = np.average(x, weights=w), np.average(l, weights=w)
    m = (w * (x - xm) * (l - lm)).sum() / (w * (x - xm) ** 2).sum()
    b = m if down else -m
    if b <= 0:
        return None
    mu = xm - lm / m
    return (mu, 1 / b) if x.min() <= mu <= x.max() else None  # mu is read between the strikes, never extrapolated


def contract_rows(t: pd.DataFrame, sign: int, start: int, end: int, ctype: str) -> pd.DataFrame:
    t = t.sort_values(["ts_s", "log_index"])
    ts = t["ts_s"].to_numpy()
    lo, p = t["log_odds"].to_numpy(), t["price_raw"].to_numpy()
    usd = t["size_usdc"].to_numpy()
    buy = np.where(t["side"].to_numpy() == "YES_BUY", 1.0, -1.0) * sign * usd
    cum = np.r_[0.0, np.cumsum(usd)]
    cs = np.r_[0.0, np.cumsum(np.where(usd < FLOOR, buy, 0.0))]
    cl = np.r_[0.0, np.cumsum(np.where(usd >= FLOOR, buy, 0.0))]
    d = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET).tz_localize(None).normalize().unique()
    M = d.tz_localize(ET).tz_convert("UTC").astype("int64") // 10**9  # midnight ET starting each trade day
    i0, i1 = np.searchsorted(ts, M, "left"), np.searchsorted(ts, M + DAY, "left")
    iD = np.searchsorted(ts, (d - pd.Timedelta(days=1)).tz_localize(ET).tz_convert("UTC").astype("int64") // 10**9, "left")  # midnight starting D
    q = (i0 > 0) & (i1 > i0) & (start <= M) & (M < end) & (cum[i0] >= FLOOR)
    i0, i1, iD, d = i0[q], i1[q], iD[q], d[q]
    p0, p1 = p[i0 - 1], p[i1 - 1]
    if sign < 0:
        p0, p1 = 1 - p0, 1 - p1
    return pd.DataFrame({"day": d - pd.Timedelta(days=1), "w": cum[i0] - cum[iD], "dv": cum[i1] - cum[i0],
                         "dl": sign * (lo[i1 - 1] - lo[i0 - 1]), "dp": (p1 - p0) / p0,
                         "fs": cs[i1] - cs[i0], "fl": cl[i1] - cl[i0],
                         "l0": lo[i0 - 1], "l1": lo[i1 - 1], "c0": cum[i0], "c1": cum[i1],
                         "big": cum[i0] >= BIG, "ctype": ctype})


def main() -> None:
    mk = pd.read_parquet("data/polymarket/contracts/markets.parquet")
    mk = mk[mk["excluded_reason"].isna() & (mk["contract_type"] != "close_bucket") & (mk["direction"] != "bucket")]
    mk = mk.set_index("condition_id")
    rows = []
    for f in sorted(Path("data/polymarket/trades").glob("contract_type=*/year=*/month=*/part-*.parquet")):
        t = pd.read_parquet(f, columns=["market_id", "ts_s", "log_index", "price_raw", "log_odds", "size_usdc", "side"])
        if t.empty or t["market_id"].iat[0] not in mk.index:
            continue
        c = mk.loc[t["market_id"].iat[0]]
        r = contract_rows(t, -1 if c["direction"] == "below" else 1,
                          int(c["start_ts_utc"].timestamp()), int(c["usable_end_ts_utc"].timestamp()), c["contract_type"])
        rows.append(r.assign(company_id=c["company_id"], event_id=c["event_id"], strike=c["strike_lo"],
                             direction=c["direction"], expiry=c["scheduled_end_ts_utc"]))
    r = pd.concat(rows, ignore_index=True)
    r["wy"], r["wm"] = r["w"] * r["dl"], r["w"] * r["dp"]
    k = ["company_id", "day"]
    out = r.groupby(k)[["w", "dv", "wy", "wm", "fs", "fl"]].sum()
    out = out.assign(y=out["wy"] / out["w"], y_money=out["wm"] / out["w"])
    big = r[r["big"]].groupby(k)[["w", "wy", "wm"]].sum()
    out["y_big"], out["y_money_big"] = big["wy"] / big["w"], big["wm"] / big["w"]
    ty = r.groupby(k + ["ctype"])[["w", "wy"]].sum()
    out = out.join((ty["wy"] / ty["w"]).unstack("ctype").add_prefix("y_type_")).reset_index()

    lr = r[r["ctype"].isin(LADDERS)].copy()  # steps 76a-76e
    lr["dir"] = np.where(lr["ctype"] == "close_ladder", "close", np.where(lr["direction"] == "below", "down", "up"))
    flip = (lr["ctype"] == "close_ladder") & (lr["direction"] == "below")  # "below" rung -> "above" rung: 1 - p
    lr["l0"], lr["l1"] = np.where(flip, -lr["l0"], lr["l0"]), np.where(flip, -lr["l1"], lr["l1"])
    edge = np.log(0.999 / 0.001) - 1e-9  # a rung at the clip only bounds the price; it cannot place the curve
    lr = lr[(lr["strike"] > 0) & (lr["l0"].abs() < edge) & (lr["l1"].abs() < edge)]
    lad = []
    for (cid, day, eid, dr, _), g in lr.groupby(k + ["event_id", "dir", "expiry"]):  # a re-listed rung is its own ladder
        if len(g) < 2:
            continue
        x = np.log(g["strike"].to_numpy(float))
        if not all(g[c].min() <= 0 <= g[c].max() for c in ("l0", "l1")):  # rungs must straddle even odds at both times
            continue
        f0 = ladder_fit(x, g["l0"].to_numpy(), g["c0"].to_numpy(), dr == "down")
        f1 = ladder_fit(x, g["l1"].to_numpy(), g["c1"].to_numpy(), dr == "down")
        if f0 and f1:
            lad.append((cid, day, eid, dr, len(g), f0[0], f1[0], f0[1], f1[1], f1[0] - f0[0],
                        np.log(f1[1]) - np.log(f0[1]), g["w"].sum()))
    lad = pd.DataFrame(lad, columns=k + ["event_id", "direction", "n_rungs", "mu0", "mu1", "s0", "s1", "dmu", "dlog_s", "weight"])
    lad.to_parquet("data/news/ladder_reactions.parquet", index=False)
    lad["wm"], lad["ws"] = lad["weight"] * lad["dmu"], lad["weight"] * lad["dlog_s"]
    cl = lad.groupby(k)[["weight", "wm", "ws"]].sum()  # step 76f
    cl = pd.DataFrame({"y_ladder": cl["wm"] / cl["weight"], "dlog_s": cl["ws"] / cl["weight"]}).reset_index()
    out = out.merge(cl, on=k, how="left")
    out = out.rename(columns={"dv": "dv_pm_24h", "fs": "flow_small", "fl": "flow_large"}).drop(columns=["w", "wy", "wm"])

    px = pd.read_parquet("data/stocks/prices.parquet", columns=["company_id", "date", "adj_close"])
    px["date"] = pd.to_datetime(px["date"])
    ys = []
    for cid, p in px.dropna().groupby("company_id"):
        s = p.drop_duplicates("date").set_index("date")["adj_close"].sort_index()
        o = out.loc[out["company_id"] == cid, ["day"]]
        prev = s.index.searchsorted(o["day"].to_numpy(), "right") - 1  # last close on or before D
        nxt = s.reindex(o["day"] + pd.Timedelta(days=1)).to_numpy()  # NaN unless D+1 is a trading day
        ys.append(pd.Series(nxt / s.to_numpy()[np.maximum(prev, 0)] - 1, index=o.index).where(prev >= 0))
    out["y_stock"] = pd.concat(ys) if ys else np.nan
    out = out.sort_values(["day", "company_id"]).reset_index(drop=True)
    out.to_parquet("data/news/reactions.parquet", index=False)
    print(f"{len(out)} company-days, {int(out['y_stock'].notna().sum())} with y_stock -> data/news/reactions.parquet")


if __name__ == "__main__":
    main()
