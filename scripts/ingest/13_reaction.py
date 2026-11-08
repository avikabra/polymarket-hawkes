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
M is midnight Eastern after D; the window is [M, M + 24h). A contract counts when it is not a
closing bucket, has a single direction, is open at M (start <= M < actual end), has >= $1,000 traded
before M, and has a trade in the window. Weights are each contract's dollars traded on D, the
Eastern calendar day before M (known at M); a contract with none on D has weight 0.
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
                          int(c["start_ts_utc"].timestamp()), int(c["end_ts_utc"].timestamp()), c["contract_type"])
        rows.append(r.assign(company_id=c["company_id"]))
    r = pd.concat(rows, ignore_index=True)
    r["wy"], r["wm"] = r["w"] * r["dl"], r["w"] * r["dp"]
    k = ["company_id", "day"]
    out = r.groupby(k)[["w", "dv", "wy", "wm", "fs", "fl"]].sum()
    out = out.assign(y=out["wy"] / out["w"], y_money=out["wm"] / out["w"])
    big = r[r["big"]].groupby(k)[["w", "wy", "wm"]].sum()
    out["y_big"], out["y_money_big"] = big["wy"] / big["w"], big["wm"] / big["w"]
    ty = r.groupby(k + ["ctype"])[["w", "wy"]].sum()
    out = out.join((ty["wy"] / ty["w"]).unstack("ctype").add_prefix("y_type_")).reset_index()
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
