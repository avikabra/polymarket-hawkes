"""Steps 74 to 78: the Polymarket reaction y(k,D), the stock reaction y^S(k,D) and the standardized reaction xi.

    uv run python scripts/ingest/13_reaction.py [--day midnight|close]

Reads data/polymarket/contracts/markets.parquet, the trades (03), data/stocks/prices.parquet.
Output data/news/reactions.parquet (close mode: reactions_close.parquet), one row per company-day with at
least one qualifying contract:
  y          dollar-weighted mean of sign * (log-odds(last trade < t1) - log-odds(last trade < t0)),
             weights = each contract's dollars traded in the 24 hours before t0 (steps 76-77); null if all are 0
  y_money    same weights, mean of (p' - p) / p with p the good-news-side price (step 77)
  y_stock    adj_close of the next day / adj_close of the last day <= D, minus 1; only when D+1 trades
  dv_pm_24h, flow_small, flow_large   24h dollars, and net good-news-side flow (buys - sells) in
             trades under / at least $1,000 (steps 104-105)
  y_big, y_money_big   y and y_money over contracts with >= $10,000 traded before t0 (step 96)
  y_type_<contract_type>   y over the company's contracts of that type (null if none that day)
  Steps 78a-78f, over contracts with a strike (close and barrier ladders), weights as y; suffix _h10/_h20/_h60
  is the half-life of sigma (78a):
  y_xi       weighted mean of xi_c (78c, 78e)         xi_hat_h*  weighted mean of xi_hat_c (78d)
  m_xi_h*    y_xi - xi_hat_h*                         y_imp_h*   weighted mean of the model log-odds change
  y_strike   weighted mean of the step-76 log-odds change dl over the same contracts that enter y_imp_h*
  m_h*       y_strike - y_imp_h*  (like for like: both over the contracts with a strike and a xi)
  r_std_D_h*, r_std_Dm1_h*   stock log return on the last session <= D (and the session before) / previous-day
             sigma/sqrt(252)                         g0_h*  weighted mean of (z_c - zhat_c) sqrt(tau0)/sqrt(dt)
Also data/news/xi_contracts.parquet (xi_contracts_close.parquet), one row per contract-day with an xi:
company_id, day, condition_id, kind (close | up | down), p0, p1, tau0, tau1, dt, xi, xi_hat_h20, weight, and for the
bootstrap in 15_score.py strike, S0, S1, below (direction == "below"), z0 (the z of p0, step 78c).
Window (step 74, 78g): midnight mode t0 = midnight Eastern after D, t1 = t0 + 24h. Close mode (78g): D is an NYSE
session, t0 = its 16:00 close, t1 = 16:00 close of the next session, weights = dollars in [t0 - 24h, t0).
A contract counts when it is not a closing bucket, has a single direction, is open at t0 (start <= t0 < actual
end), has >= $1,000 traded before t0, and has a trade in the window. xi needs dt > 0 and the contract not
settling or expiring inside the window. Barrier = barrier_ladder, or a close_ladder whose question says
hit/reach/touch/dip. tau = NYSE sessions to the scheduled end / 252, a session in progress by its share of 6.5 h.
sign = +1 when YES pays if the stock rises or the contract has no direction (earnings, up/down,
"above"), -1 for "below". Buying the good-news side = YES_BUY when sign = +1, YES_SELL when -1
(side is already in YES terms, 03). Log-odds only; price_raw is clipped to (0.001, 0.999).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import log_ndtr, logit, ndtr, ndtri

ET = "America/New_York"
DAY = 86400
FLOOR = 1000.0
BIG = 10000.0
STRIKE_TYPES = ["close_ladder", "barrier_ladder"]
HALF_LIVES = [10, 20, 60]
XI_P = (0.05, 0.95)  # step 85a, locked on training days: xi fails at the price extremes (tick floor)
XI_MAX_DAYS = 20  # step 85a: beyond 20 trading days left, too few contracts and an unstable mean xi^2
HIT = re.compile(r"\b(hit|reach|touch|dip)\b")


def et_ts(d, hour: float) -> np.ndarray:
    """UTC seconds of `hour` o'clock Eastern on each (naive) date."""
    return ((pd.DatetimeIndex(d) + pd.Timedelta(hours=hour)).tz_localize(ET).tz_convert("UTC").astype("int64") // 10**9).to_numpy()


def trading_time(ts, sess: pd.DatetimeIndex) -> np.ndarray:
    """Step 78b: NYSE sessions elapsed at UTC seconds ts; a session in progress counts its share of 6.5 h
    since 09:30 ET, and at midnight the next session is whole."""
    t = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET)
    d = t.tz_localize(None).normalize()
    k = sess.searchsorted(d)
    on = (k < len(sess)) & (sess[np.minimum(k, len(sess) - 1)] == d)
    h = np.asarray(t.hour + t.minute / 60 + t.second / 3600)
    out = k + np.where(on, np.clip((h - 9.5) / 6.5, 0, 1), 0)
    return np.where(d > sess[-1] + pd.Timedelta(days=4), np.nan, out)


def model(S, K, sig, tau, kind):
    """Step 78d: model price in the z frame and its z. Close: Phi(d) (probability of closing above K), z = d.
    Barrier: GBM first-passage probability with log-drift -sig^2/2, z = Phi^-1(1 - P/2).
    Up barrier (x = ln(K/S) > 0, drift mu = -sig^2/2):  P = Phi((-x + mu tau)/s) + exp(2 mu x/sig^2) Phi((-x - mu tau)/s).
    Down barrier (x = ln(S/K) > 0): the log price -ln S has drift +sig^2/2, so the same formula with mu = +sig^2/2."""
    up = kind == "up"
    s, v = sig * np.sqrt(tau), sig ** 2 * tau / 2
    ln = np.log(S / K)
    with np.errstate(all="ignore"):
        d = (ln - v) / s
        x = np.where(up, -ln, ln)
        c = np.where(up, -v, v)  # mu tau
        P = ndtr((-x + c) / s) + np.exp(np.where(up, -x, x) + log_ndtr((-x - c) / s))
        P = np.where(x <= 0, 1.0, np.clip(P, 1e-12, 1))
        return np.where(kind == "close", ndtr(d), P), np.where(kind == "close", d, ndtri(1 - P / 2))


def contract_rows(t: pd.DataFrame, sign: int, start: int, end: int, ctype: str, sess: pd.DatetimeIndex, close: bool) -> pd.DataFrame:
    t = t.sort_values(["ts_s", "log_index"])
    ts = t["ts_s"].to_numpy()
    lo, p = t["log_odds"].to_numpy(), t["price_raw"].to_numpy()
    usd = t["size_usdc"].to_numpy()
    buy = np.where(t["side"].to_numpy() == "YES_BUY", 1.0, -1.0) * sign * usd
    cum = np.r_[0.0, np.cumsum(usd)]
    cs = np.r_[0.0, np.cumsum(np.where(usd < FLOOR, buy, 0.0))]
    cl = np.r_[0.0, np.cumsum(np.where(usd >= FLOOR, buy, 0.0))]
    d = pd.to_datetime(ts, unit="s", utc=True).tz_convert(ET).tz_localize(None).normalize().unique()
    if close:  # step 78g: close of session D to close of the next session
        lo_i, hi_i = sess.searchsorted(d.min()), min(sess.searchsorted(d.max(), "right"), len(sess) - 1)
        day = sess[lo_i:hi_i]
        t0, t1, tw = et_ts(day, 16), et_ts(sess[lo_i + 1:hi_i + 1], 16), et_ts(day - pd.Timedelta(days=1), 16)
    else:  # midnight Eastern after D, for 24 hours
        day = d - pd.Timedelta(days=1)
        t0 = et_ts(d, 0)
        t1, tw = t0 + DAY, et_ts(day, 0)
    i0, i1, iD = np.searchsorted(ts, t0, "left"), np.searchsorted(ts, t1, "left"), np.searchsorted(ts, tw, "left")
    q = (i0 > 0) & (i1 > i0) & (start <= t0) & (t0 < end) & (cum[i0] >= FLOOR)
    i0, i1, iD, day, t0, t1 = i0[q], i1[q], iD[q], day[q], t0[q], t1[q]
    q0, q1 = p[i0 - 1], p[i1 - 1]
    p0, p1 = (1 - q0, 1 - q1) if sign < 0 else (q0, q1)
    return pd.DataFrame({"day": day, "w": cum[i0] - cum[iD], "dv": cum[i1] - cum[i0],
                         "dl": sign * (lo[i1 - 1] - lo[i0 - 1]), "dp": (p1 - p0) / p0,
                         "fs": cs[i1] - cs[i0], "fl": cl[i1] - cl[i0],
                         "big": cum[i0] >= BIG, "ctype": ctype, "t0": t0, "t1": t1,
                         "q0": np.clip(q0, 0.001, 0.999), "q1": np.clip(q1, 0.001, 0.999)})


def attach(df: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    """Add the stock row of the last session <= day (sorted by day)."""
    left = df.assign(day=df["day"].astype("datetime64[ns]")).sort_values("day")
    return pd.merge_asof(left, st.sort_values("date"), left_on="day", right_on="date", by="company_id")  # right keys sorted by date alone


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", choices=["midnight", "close"], default="midnight", help="step 78g day definition")
    close = ap.parse_args().day == "close"
    sfx = "_close" if close else ""

    px = pd.read_parquet("data/stocks/prices.parquet", columns=["company_id", "date", "close", "adj_close"])
    px["date"] = pd.to_datetime(px["date"]).astype("datetime64[ns]")
    sess = pd.DatetimeIndex(np.sort(px.loc[px["company_id"] == "spy", "date"].unique()))  # NYSE sessions
    st = px.dropna().drop_duplicates(["company_id", "date"]).sort_values(["company_id", "date"]).reset_index(drop=True)
    sh = lambda c, n: st.groupby("company_id")[c].shift(n)
    st["r"] = np.log(st["adj_close"]).groupby(st["company_id"]).diff()
    st["S0"], st["S1"], st["adj_next"], st["date_next"] = st["close"], sh("close", -1), sh("adj_close", -1), sh("date", -1)
    for h in HALF_LIVES:  # step 78a, daily scale
        st[f"sd{h}"] = st.groupby("company_id")["r"].transform(lambda r: (r ** 2).ewm(halflife=h, min_periods=20).mean() ** 0.5)
        st[f"r_std_D_h{h}"] = st["r"] / sh(f"sd{h}", 1)
        st[f"r_std_Dm1_h{h}"] = sh("r", 1) / sh(f"sd{h}", 2)

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
                          int(c["start_ts_utc"].timestamp()), int(c["usable_end_ts_utc"].timestamp()), c["contract_type"], sess, close)
        kind = None  # contracts with a strike (78e): close, up barrier, down barrier
        if c["contract_type"] in STRIKE_TYPES and c["strike_lo"] > 0 and c["direction"] in ("above", "below"):
            bar = c["contract_type"] == "barrier_ladder" or bool(HIT.search(str(c["question"])))
            kind = ("up" if c["direction"] == "above" else "down") if bar else "close"
        rows.append(r.assign(company_id=c["company_id"], cond=t["market_id"].iat[0], strike=c["strike_lo"], direction=c["direction"], kind=kind,
                             exp=0 if pd.isna(c["scheduled_end_ts_utc"]) else int(c["scheduled_end_ts_utc"].timestamp()),
                             stl=np.inf if pd.isna(c["settled_ts_utc"]) else int(c["settled_ts_utc"].timestamp())))
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

    # steps 78b-78e: xi_c, xi_hat_c, model log-odds change and g0 for every contract with a strike
    s = attach(r[r["kind"].notna()], st)
    tau = [(trading_time(s["exp"].to_numpy(), sess) - trading_time(s[c].to_numpy(), sess)) / 252 for c in ("t0", "t1")]
    s["tau0"], s["tau1"] = tau
    s["dt"] = s["tau0"] - s["tau1"]
    s = s[(s["dt"] > 1e-9) & (s["tau1"] > 1e-9) & (s["exp"] > s["t1"]) & (s["stl"] > s["t1"])].copy()  # no weekend window, no settling inside
    kind, below = s["kind"].to_numpy(), (s["direction"] == "below").to_numpy()
    sgn = np.where(kind == "up", -1.0, 1.0)  # xi > 0 is good news: + close-above and down-barrier, - up-barrier
    zc = lambda q: np.where(kind == "close", ndtri(np.where(below, 1 - q, q)), ndtri(1 - q / 2))  # step 78c
    z0, z1 = zc(s["q0"].to_numpy()), zc(s["q1"].to_numpy())
    r0, r1, rd = np.sqrt(s["tau0"].to_numpy()), np.sqrt(s["tau1"].to_numpy()), np.sqrt(s["dt"].to_numpy())
    s["xi"], s["below"], s["z0"] = sgn * (z1 * r1 - z0 * r0) / rd, below, z0
    for h in HALF_LIVES:
        sig, K = s[f"sd{h}"].to_numpy() * np.sqrt(252), s["strike"].to_numpy(float)
        P0, zh0 = model(s["S0"].to_numpy(), K, sig, r0 ** 2, kind)
        P1, zh1 = model(s["S1"].to_numpy(), K, sig, r1 ** 2, kind)
        s[f"xi_hat_h{h}"] = sgn * (zh1 * r1 - zh0 * r0) / rd
        s[f"g0_h{h}"] = sgn * (z0 - zh0) * r0 / rd
        yes = lambda P: np.clip(np.where(below & (kind == "close"), 1 - P, P), 0.001, 0.999)  # model YES price
        s[f"y_imp_h{h}"] = np.where(below, -1, 1) * (logit(yes(P1)) - logit(yes(P0)))  # step 74 sign flip
    cols = ["xi", "dl"] + [f"{a}_h{h}" for a in ("xi_hat", "g0", "y_imp") for h in HALF_LIVES]
    s = s[np.isfinite(s[cols]).all(axis=1)]
    s[["company_id", "day", "cond", "kind", "q0", "q1", "tau0", "tau1", "dt", "xi", "xi_hat_h20", "w", "strike", "S0", "S1", "below", "z0"]].rename(
        columns={"cond": "condition_id", "q0": "p0", "q1": "p1", "w": "weight"}).to_parquet(f"data/news/xi_contracts{sfx}.parquet", index=False)
    s = s[s["q0"].between(*XI_P) & (s["tau0"] * 252 <= XI_MAX_DAYS)]  # the contract file above keeps every contract
    sw = s[cols].mul(s["w"], axis=0).assign(company_id=s["company_id"], day=s["day"], w=s["w"]).groupby(k)[cols + ["w"]].sum()
    xs = sw[cols].div(sw["w"], axis=0).rename(columns={"xi": "y_xi", "dl": "y_strike"}).reset_index()
    out = out.merge(xs, on=k, how="left")
    for h in HALF_LIVES:
        out[f"m_xi_h{h}"] = out["y_xi"] - out[f"xi_hat_h{h}"]
        out[f"m_h{h}"] = out["y_strike"] - out[f"y_imp_h{h}"]
    # step 99: the stock's standardized return over the window = xi_hat of any close contract (the same for every strike)
    cw = s[s["kind"] == "close"].groupby(k)[[f"xi_hat_h{h}" for h in HALF_LIVES]].first()
    out = out.merge(cw.rename(columns=lambda c: c.replace("xi_hat", "r_win")).reset_index(), on=k, how="left")

    # controls (78f) and the stock reaction (78): the stock row of the last session <= D
    m = attach(out[k], st)
    nxt = (m["date"] == m["day"]) if close else (m["date_next"] == m["day"] + pd.Timedelta(days=1))  # close: D a session; else D+1 trades
    m["y_stock"] = (m["adj_next"] / m["adj_close"] - 1).where(nxt)
    out = out.merge(m[k + ["y_stock"] + [f"r_std_{a}_h{h}" for a in ("D", "Dm1") for h in HALF_LIVES]], on=k, how="left")
    out = out.sort_values(["day", "company_id"]).reset_index(drop=True)
    out.to_parquet(f"data/news/reactions{sfx}.parquet", index=False)
    print(f"{len(out)} company-days, {int(out['y_stock'].notna().sum())} with y_stock, {int(out['y_xi'].notna().sum())} with y_xi -> data/news/reactions{sfx}.parquet")


if __name__ == "__main__":
    main()
