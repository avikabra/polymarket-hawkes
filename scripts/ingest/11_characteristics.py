"""Steps 47 to 60 (raw values only): the JKP characteristics for every company and day.

For company k and day D (Eastern time) every number uses data through D-1. A month is one
calendar month counted back from D-1. Raw values only: no ranking and no blending here (step 58).

    uv run python scripts/ingest/11_characteristics.py

Reads data/stocks/{prices,rf,fx,statements}.parquet (script 10; statements in a non-USD financial
currency, i.e. TSMC in Taiwan dollars, are converted to USD at the period-end rate, step 49), the stored companiesmarketcap
files data/stocks/cmc/<company_id>.json (load_cmc: market cap, and total assets and liabilities
only at points within 7 days of a month-end, standing for a period end, step 72),
data/polymarket/contracts/markets.parquet and the trades.
Writes data/news/pm_daily.parquet (company_id, day, r_pm, dv_pm) and
data/news/characteristics.parquet (company_id, day, beta, me, bm, prof, inv, mom_s, mom_pm,
vol_s, vol_pm, ill_s, ill_pm, industry).
Windows: mom = months t-12..t-2 (the span the return uses), vol = last month, ill = last 6 months.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import duckdb
import numpy as np
import pandas as pd
import yaml

from src.utils import get_logger

log = get_logger(__name__)
STOCKS, NEWS = Path("data/stocks"), Path("data/news")
CMC = STOCKS / "cmc"
MARKETS = Path("data/polymarket/contracts/markets.parquet")
TRADES = "data/polymarket/trades/contract_type=*/year=*/month=*/part-*.parquet"
DAYS = pd.date_range("2025-09-26", "2026-10-30")
M = pd.DateOffset


# ── step 47, 48: Polymarket daily return and dollar volume ────────────────────
def pm_daily() -> pd.DataFrame:
    # last trade of each contract-day (Eastern), and the dollars that day
    q = f"""
        SELECT t.market_id AS condition_id,
               CAST(timezone('America/New_York', to_timestamp(t.ts_s)) AS DATE) AS day,
               arg_max(least(greatest(t.price_raw, 0.001), 0.999), (t.ts_s, t.log_index)) AS p_last,
               sum(t.size_usdc) AS usd
        FROM read_parquet('{TRADES}', hive_partitioning=true) t
        GROUP BY 1, 2"""
    d = duckdb.sql(q).df()
    d["l"] = np.log(d["p_last"] / (1 - d["p_last"]))  # log-odds of the clipped price
    mk = pd.read_parquet(MARKETS, columns=["condition_id", "company_id", "contract_type", "direction"])
    d = d.merge(mk.drop_duplicates("condition_id"), on="condition_id")
    d["day"] = pd.to_datetime(d["day"])
    d = d.sort_values(["condition_id", "day"])
    g = d.groupby("condition_id")
    gap = (d["day"] - g["day"].shift()).dt.days
    d["dl"] = (d["l"] - g["l"].shift()).where(gap <= 14)  # first day and stale previous trade: no change
    d["dl"] = d["dl"] * np.where(d["direction"] == "below", -1.0, 1.0)  # up means good for the stock
    d.loc[(d["direction"] == "bucket") | (d["contract_type"] == "close_bucket"), "dl"] = np.nan
    d["w"] = d["usd"].where(d["dl"].notna(), 0.0)
    d["wdl"] = d["dl"].fillna(0.0) * d["w"]
    out = d.groupby(["company_id", "day"]).agg(wdl=("wdl", "sum"), w=("w", "sum"), dv_pm=("usd", "sum")).reset_index()
    out["r_pm"] = (out["wdl"] / out["w"]).where(out["w"] > 0)
    out = out[["company_id", "day", "r_pm", "dv_pm"]]
    out.to_parquet(NEWS / "pm_daily.parquet", index=False)
    return out


# ── step 72: stored companiesmarketcap series ─────────────────────────────────
def load_cmc(ids: list[str]) -> pd.DataFrame:
    """Long table company_id, date, market_cap, total_assets, total_liabilities (one series per row)."""
    out = []
    for c in ids:
        f = CMC / f"{c}.json"
        if not f.exists():
            continue
        j = json.load(open(f))
        def series(key, field, name):
            s = pd.DataFrame(j.get(key) or [], columns=["d", field]).dropna()
            return pd.DataFrame({"date": pd.to_datetime(s["d"], unit="s").dt.normalize(), name: s[field].astype(float)})
        out.append(series("marketcap", "m", "market_cap").assign(company_id=c))
        bal = [series(k, "v", n) for k, n in (("total-assets", "total_assets"), ("total-liabilities", "total_liabilities"))]
        bal = bal[0].merge(bal[1], on="date", how="outer").assign(company_id=c)
        # a period end sits at a month-end (52/53-week fiscal calendars end up to 7 days off it)
        near = np.minimum((bal["date"] + pd.offsets.MonthEnd(0) - bal["date"]).dt.days, bal["date"].dt.day)
        out.append(bal[near <= 7])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["company_id", "date", "market_cap", "total_assets", "total_liabilities"])


# ── step 49: statements in Taiwan dollars -> US dollars ───────────────────────
def to_usd(st: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    """Divide every field of a TWD statement row by the TWD-per-USD rate on or before its period end."""
    cur = st["financial_currency"]
    odd = sorted(cur[cur.notna() & ~cur.isin(["USD", "TWD"])].unique())
    if odd:
        log.warning("statements in a currency with no rate, left as reported", currencies=odd)
    twd = (cur == "TWD").to_numpy()
    if not twd.any():
        return st
    cols = [c for c in st.columns if c not in ("company_id", "period_end", "freq", "financial_currency")]
    i = fx["date"].to_numpy("datetime64[ns]").searchsorted(st.loc[twd, "period_end"].to_numpy("datetime64[ns]"), "right") - 1
    rate = np.where(i >= 0, fx["twd_per_usd"].to_numpy()[np.maximum(i, 0)], np.nan)  # before the first rate: missing
    st = st.copy()
    st.loc[twd, cols] = st.loc[twd, cols].div(rate, axis=0)
    return st


# ── accounting, steps 49, 52 to 54 ────────────────────────────────────────────
def accounting(st: pd.DataFrame, cmc: pd.DataFrame):
    """Per-company tables: balance rows with raw BE, and TTM income candidates."""
    bal = pd.concat([st[["period_end", "shareholders_equity", "common_equity", "preferred_stock",
                         "deferred_taxes", "total_assets", "total_liabilities"]],
                     cmc.dropna(subset=["total_assets", "total_liabilities"], how="all")
                     .rename(columns={"date": "period_end"})[["period_end", "total_assets", "total_liabilities"]]])
    bal = bal.groupby("period_end").first().sort_index()  # Yahoo values first, then the stored series
    pref = bal["preferred_stock"].fillna(0.0)
    seq = bal["shareholders_equity"].fillna(bal["common_equity"] + pref).fillna(bal["total_assets"] - bal["total_liabilities"])
    bal["be"] = seq + bal["deferred_taxes"].fillna(0.0) - pref
    inc = st.copy()
    inc["ebitda_row"] = inc["ebitda"].fillna(inc["revenue"] - inc["operating_expenses"]).fillna(inc["gross_profit"] - inc["sga"])
    ann = inc[inc["freq"] == "annual"].set_index("period_end").sort_index()
    ann = ann.assign(ebitda_ttm=ann["ebitda_row"], int_ttm=ann["interest_expense"])[["ebitda_ttm", "int_ttm"]]
    qtr = inc[inc["freq"] == "quarterly"].set_index("period_end").sort_index()
    span = pd.Series(qtr.index, index=qtr.index).diff(3).dt.days  # four quarters end within ~9 months of the first
    ok = (span >= 250) & (span <= 290)
    q = pd.DataFrame({"ebitda_ttm": qtr["ebitda_row"].rolling(4, min_periods=4).sum(),
                      "int_ttm": qtr["interest_expense"].rolling(4, min_periods=4).sum()})[ok]
    ttm = pd.concat([ann, q]).dropna().groupby(level=0).last().sort_index()
    return bal, ttm


def latest(tab: pd.DataFrame, col: str, d1: pd.Timestamp):
    """Latest value of col usable on D-1: reported 4 months after period end, expires after 18."""
    s = tab[col].dropna()
    pe = s.index
    s = s[(pe + M(months=4) <= d1) & (pe >= d1 - M(months=18))]
    return s.iloc[-1] if len(s) else np.nan


def window(dates: np.ndarray, d1: pd.Timestamp, months: int, skip: int = 0):
    """Slice bounds of trading days in (D-1 - months, D-1 - skip months]."""
    hi, lo = d1 - M(months=skip), d1 - M(months=months)
    return np.searchsorted(dates, np.datetime64(lo), "right"), np.searchsorted(dates, np.datetime64(hi), "right")


def main() -> None:
    NEWS.mkdir(parents=True, exist_ok=True)
    cos = yaml.safe_load(open("config/companies.yaml"))["companies"]
    ids = [c["id"] for c in cos]
    industry = {i: g for g, v in yaml.safe_load(open("config/gics.yaml")).items() for i in v}
    pm = pm_daily()
    log.info("pm_daily", rows=len(pm))

    px = pd.read_parquet(STOCKS / "prices.parquet").sort_values(["company_id", "date"])
    rf = pd.read_parquet(STOCKS / "rf.parquet").sort_values("date")
    fx = pd.read_parquet(STOCKS / "fx.parquet").sort_values("date")
    st = to_usd(pd.read_parquet(STOCKS / "statements.parquet"), fx)
    cmc = load_cmc(ids)
    # daily total return, excess return and dollar volume on each company's trading days
    rfs = rf.set_index("date")["rf_daily"]
    px["rf"] = rfs.reindex(rfs.index.union(px["date"].unique())).ffill().reindex(px["date"]).values
    px["r"] = px.groupby("company_id")["adj_close"].pct_change()
    px["rx"] = px["r"] - px["rf"]
    px["dv"] = px["close"] * px["volume"]
    cmc = cmc.sort_values("date")
    acct = {c: accounting(st[st["company_id"] == c], cmc[cmc["company_id"] == c]) for c in ids}
    caps = {c: g.dropna(subset=["market_cap"]) for c, g in cmc.groupby("company_id")}
    S = {k: g for k, g in px.groupby("company_id")}
    P = {k: g for k, g in pm.sort_values("day").groupby("company_id")}
    mkt = S["spy"]

    # month grid: 61 boundaries per day, monthly returns of stocks and market, trimmed across companies
    def px_at(g, bounds):
        i = np.searchsorted(g["date"].values, bounds.values, "right") - 1
        return np.where(i >= 0, g["adj_close"].values[np.maximum(i, 0)], np.nan)

    rows = []
    for D in DAYS:
        d1 = D - pd.Timedelta(days=1)
        bounds = pd.DatetimeIndex([d1 - M(months=j) for j in range(61)])
        rf_m = rfs.reindex(rfs.index.union(bounds)).ffill().reindex(bounds).values[:-1] * 21
        pm_ = px_at(mkt, bounds)
        mk_ex = pm_[:-1] / pm_[1:] - 1 - rf_m
        raw = {k: px_at(S[k], bounds) for k in ids if k in S}
        ret = {k: v[:-1] / v[1:] - 1 for k, v in raw.items()}
        ex = np.array([ret[k] - rf_m for k in ret])
        lo, hi = np.nanpercentile(ex, [0.1, 99.9], axis=0) if np.isfinite(ex).any() else (None, None)
        ex_t = np.clip(ex, lo, hi) if lo is not None else ex
        ex_row = dict(zip(ret, ex_t))
        for c in ids:
            r = dict(company_id=c, day=D, industry=industry.get(c))
            g, h = S.get(c), P.get(c)
            if g is not None:
                dt = g["date"].values
                # beta: 60 monthly excess returns (36 minimum), zero-return months left out
                use = np.isfinite(ex_row[c]) & np.isfinite(mk_ex) & (ret[c] != 0)
                if use.sum() >= 36:
                    x, y = mk_ex[use], ex_row[c][use]
                    r["beta"] = np.cov(x, y)[0, 1] / np.var(x, ddof=1)
                # size and book-to-market
                cm = caps.get(c, cmc.iloc[:0])
                cm = cm[cm["date"] <= d1]
                j = np.searchsorted(dt, np.datetime64(d1), "right") - 1
                if len(cm) and j >= 0:
                    k0 = np.searchsorted(dt, np.datetime64(cm["date"].iloc[-1]), "right") - 1
                    if k0 >= 0:
                        r["me"] = cm["market_cap"].iloc[-1] * g["close"].values[j] / g["close"].values[k0]
                # momentum: price 1 month ago over price 12 months ago
                i1, i12 = np.searchsorted(dt, np.datetime64(bounds[1]), "right") - 1, np.searchsorted(dt, np.datetime64(bounds[12]), "right") - 1
                if i12 >= 0:
                    r["mom_s"] = g["adj_close"].values[i1] / g["adj_close"].values[i12] - 1
                a, b = window(dt, d1, 1)
                rx, r0 = g["rx"].values[a:b], g["r"].values[a:b]
                if np.isfinite(rx).sum() >= 15 and (r0 == 0).sum() < 10:
                    r["vol_s"] = np.nanstd(rx, ddof=1)
                a, b = window(dt, d1, 6)
                ok = np.isfinite(g["r"].values[a:b]) & (g["dv"].values[a:b] > 0)
                if ok.sum() >= 60:
                    r["ill_s"] = np.mean(np.abs(g["r"].values[a:b][ok]) / g["dv"].values[a:b][ok]) * 1e6
            if h is not None:  # no Polymarket trades at all: the three Polymarket versions stay missing
                dd = h["day"].values
                a, b = window(dd, d1, 12, skip=1)
                if dd[0] <= np.datetime64(bounds[12]) and np.isfinite(h["r_pm"].values[a:b]).any():
                    r["mom_pm"] = np.nansum(h["r_pm"].values[a:b])  # log-odds changes add
                a, b = window(dd, d1, 1)
                rp = h["r_pm"].values[a:b]
                if np.isfinite(rp).sum() >= 15 and (rp == 0).sum() < 10:
                    r["vol_pm"] = np.nanstd(rp, ddof=1)
                a, b = window(dd, d1, 6)
                rp, dv = h["r_pm"].values[a:b], h["dv_pm"].values[a:b]
                ok = np.isfinite(rp) & (dv > 0)
                if ok.sum() >= 60:
                    r["ill_pm"] = np.mean(np.abs(rp[ok]) / dv[ok]) * 1e6
            # accounting: book equity, profitability, investment
            bal, ttm = acct[c]
            if len(bal):
                be = latest(bal, "be", d1)
                be = be if be > 0 else np.nan  # BE of 0 or less is missing
                if "me" in r and np.isfinite(be):
                    r["bm"] = be / r["me"]
                if np.isfinite(be):
                    pe = ttm.index
                    t = ttm[(pe + M(months=4) <= d1) & (pe >= d1 - M(months=18))]
                    if len(t):
                        r["prof"] = (t["ebitda_ttm"].iloc[-1] - t["int_ttm"].iloc[-1]) / be
                a0, a1 = latest(bal, "total_assets", d1), latest(bal, "total_assets", d1 - M(years=1))
                if a1 > 0:
                    r["inv"] = a0 / a1 - 1
            rows.append(r)
        if D.day == 1:
            log.info("characteristics", day=str(D.date()))
    cols = ["company_id", "day", "beta", "me", "bm", "prof", "inv", "mom_s", "mom_pm", "vol_s", "vol_pm", "ill_s", "ill_pm", "industry"]
    out = pd.DataFrame(rows).reindex(columns=cols)
    out.to_parquet(NEWS / "characteristics.parquet", index=False)
    log.info("done", rows=len(out))


if __name__ == "__main__":
    main()
