"""Steps 92 to 107: score the test-period portfolios from 14_msrr.py. Run once, after every choice is locked.

Inputs: data/analysis/{portfolio_returns,test_weights,ridge_check}.parquet from 14_msrr.py,
data/news/reactions.parquet (needs company_id, day, y, y_money, y_stock, y_ladder, dv_pm_24h, flow_small,
flow_large) and the trade files under data/polymarket/trades (size_usdc, for step 103).

    uv run python scripts/analysis/15_score.py

Writes data/analysis/results/*.csv and summary.md. All Sharpe ratios are per day, before costs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

A = Path("data/analysis")
RES = A / "results"
TEST_START = pd.Timestamp("2026-08-28")
B = 10_000
rng = np.random.default_rng(0)


def sharpe(x):
    return x.mean() / x.std(ddof=1)


UNIT = {"y": "log-odds (step 74)", "y_same": "log-odds (step 74)", "y_big": "log-odds (step 74)",
        "y_money": "money (step 77)", "y_money_big": "money (step 77)", "y_stock": "stock return (step 78)",
        "y_ladder": "log price (step 76e)"}


def unit(target):
    return UNIT.get(target, "log-odds (step 74)" if target.startswith("y_type_") else "?")


def sharpe_row(s, **keys):
    """Point out-of-sample Sharpe ratio over the test days, as Kelly et al. report it (step 95: no intervals)."""
    s = s.dropna()
    return {**keys, "n_days": len(s), "mean": s.mean(), "sd": s.std(ddof=1), "sharpe": sharpe(s)}


def gap_row(a, b, **keys):
    sub = pd.concat([a, b], axis=1).dropna()
    return {**keys, "n_days": len(sub), "gap": sharpe(sub.iloc[:, 0]) - sharpe(sub.iloc[:, 1])}


def ols(x, yv, day):
    """y = a + c x with day-clustered standard error for c."""
    xc = x - x.mean()
    c = (xc * yv).sum() / (xc ** 2).sum()
    e = yv - yv.mean() - c * xc
    se = np.sqrt((pd.Series(xc * e).groupby(day.to_numpy()).sum() ** 2).sum()) / (xc ** 2).sum()
    r2 = 1 - (e ** 2).sum() / ((yv - yv.mean()) ** 2).sum()
    return {"a": yv.mean() - c * x.mean(), "c": c, "se": se, "t": c / se, "r2": r2, "n": len(x)}


def main():
    RES.mkdir(parents=True, exist_ok=True)
    pr = pd.read_parquet(A / "portfolio_returns.parquet")
    pr = pr[pr["day"] >= TEST_START]
    W = pd.read_parquet(A / "test_weights.parquet")
    rx = pd.read_parquet("data/news/reactions.parquet")
    rx["day"] = pd.to_datetime(rx["day"]).dt.normalize()
    R = {k: g.set_index("day")["R"] for k, g in pr.groupby(["method", "predictor", "target"])}

    # steps 93, 96, 97: Sharpe of every portfolio, each labelled with its unit
    rows = [sharpe_row(s, method=k[0], predictor=k[1], target=k[2], unit=unit(k[2])) for k, s in R.items()]
    sh = pd.DataFrame(rows)
    sh.to_csv(RES / "sharpe.csv", index=False)
    # step 95: Kelly et al. Figure 4, news shock vs raw news vs predictable news, in money and in log-odds
    fig4 = sh[(sh.method == "msrr") & sh.predictor.isin(["u", "E", "Sbeta"]) & sh.target.isin(["y_money", "y"])] \
        .pivot(index="predictor", columns="unit", values="sharpe").reindex(["u", "E", "Sbeta"])
    fig4.index = fig4.index.map({"u": "news shock (u)", "E": "raw news (E)", "Sbeta": "predictable news (S beta)"})
    fig4.reset_index().to_csv(RES / "figure4_sharpe.csv", index=False)

    # steps 96, 98: gaps of the point Sharpe ratios, pure news minus raw news (each target) and Polymarket minus stock
    gaps = []
    for t in sorted({k[2] for k in R if k[0] == "msrr"}):
        if ("msrr", "u", t) in R and ("msrr", "E", t) in R:
            gaps.append(gap_row(R["msrr", "u", t], R["msrr", "E", t], comparison="u minus E", target=t))
    for p in ["u", "E", "Sbeta", "u_frozen"]:
        if ("msrr", p, "y_same") in R and ("msrr", p, "y_stock") in R:
            gaps.append(gap_row(R["msrr", p, "y_same"], R["msrr", p, "y_stock"], comparison=f"{p}: Polymarket minus stock", target="y_same vs y_stock"))
    gaps = pd.DataFrame(gaps)
    gaps.to_csv(RES / "gaps.csv", index=False)

    # step 94: R2_OOS of the ridge check
    ck = pd.read_parquet(A / "ridge_check.parquet")
    r2 = ck.groupby("predictor").apply(lambda g: pd.Series({
        "r2_oos": 1 - ((g["y"] - g["yhat"]) ** 2).sum() / (g["y"] ** 2).sum(), "n": len(g)}), include_groups=False)
    r2.reset_index().to_csv(RES / "r2_oos.csv", index=False)

    # step 99: y = a + c * (stock return in %), all test company-days
    d = rx[rx["day"] >= TEST_START].dropna(subset=["y", "y_stock"])
    follow = [{"sample": "all", **ols(100 * d["y_stock"], d["y"], d["day"])}]
    d = rx[rx["day"] >= TEST_START].dropna(subset=["y_ladder", "y_stock"])  # y_ladder on log(1 + y_stock), both log price
    follow.append({"sample": "y_ladder on log stock return", **ols(np.log1p(d["y_stock"]), d["y_ladder"], d["day"])})
    pd.DataFrame(follow).to_csv(RES / "stock_follow.csv", index=False)

    # steps 100 to 102: the pure-news weights (fitted on Polymarket log-odds y) applied to both markets
    # on the same company-days: Polymarket money return (step 77) and stock return (step 78) per day
    pn = W[(W["method"] == "msrr") & (W["predictor"] == "u") & (W["target"] == "y")] \
        .merge(rx[["company_id", "day", "y_money", "y_stock"]], on=["company_id", "day"]).dropna(subset=["y_money", "y_stock"])
    daily = pd.DataFrame({"pm": (pn["w"] * pn["y_money"]).groupby(pn["day"]).sum(),
                          "stock": (pn["w"] * pn["y_stock"]).groupby(pn["day"]).sum()})
    f = ols(daily["stock"], daily["pm"], daily.index.to_series())  # step 101: pm = a + c * stock over test days
    x, v = daily["stock"].to_numpy(), daily["pm"].to_numpy()
    ix = rng.integers(0, len(x), (B, len(x)))  # step 102: resample test days
    xb, vb = x[ix], v[ix]
    xc, vc = xb - xb.mean(1, keepdims=True), vb - vb.mean(1, keepdims=True)
    cb = (xc * vc).sum(1) / (xc ** 2).sum(1)
    ab = vb.mean(1) - cb * xb.mean(1)
    r2b = (xc * vc).sum(1) ** 2 / ((xc ** 2).sum(1) * (vc ** 2).sum(1))
    pure = pd.DataFrame([{"param": nm, "est": f[nm], "lo": np.percentile(bs, 2.5), "hi": np.percentile(bs, 97.5), "n_days": len(daily)}
                         for nm, bs in (("a", ab), ("c", cb), ("r2", r2b))])
    pure.to_csv(RES / "pure_news_two_markets.csv", index=False)

    # step 103: trade sizes only (no claim about who trades)
    tr = pd.read_parquet("data/polymarket/trades", columns=["size_usdc"])["size_usdc"]
    big = tr >= 1000
    pd.DataFrame([{"trades": len(tr), "usd": tr.sum(), "median": tr.median(), "share_under_100": (tr < 100).mean(),
                   "share_1000_plus_count": big.mean(), "share_1000_plus_usd": tr[big].sum() / tr.sum()}]
                 ).to_csv(RES / "trade_sizes.csv", index=False)

    # steps 104 to 106 use the log-odds weights of each predictor (target y)
    w = W[(W["method"] == "msrr") & (W["target"] == "y")].merge(
        rx[["company_id", "day", "dv_pm_24h", "flow_small", "flow_large"]], on=["company_id", "day"])
    w["tercile"] = pd.qcut(w["dv_pm_24h"], 3, labels=["thin", "middle", "busy"])  # step 104
    ter = []
    for (p, tc), g in w.groupby(["predictor", "tercile"], observed=True):
        s = (g["w"] * g["y"]).groupby(g["day"]).sum()
        ter.append(sharpe_row(s, predictor=p, tercile=tc))
    pd.DataFrame(ter).to_csv(RES / "volume_terciles.csv", index=False)

    flow = []  # step 105: net good-news-side dollars on w
    for p, g in w[w["predictor"].isin(["u", "E", "Sbeta"])].groupby("predictor"):
        for f in ["flow_small", "flow_large"]:
            g2 = g.dropna(subset=[f])
            flow.append({"predictor": p, "flow": f, **ols(g2["w"], g2[f], g2["day"])})
    pd.DataFrame(flow).to_csv(RES / "flow_regression.csv", index=False)

    cap = []  # step 106: dollars traded in the contracts held (w != 0)
    for p, g in w.groupby("predictor"):
        h = g[g["w"] != 0]
        cap.append({"predictor": p, "mean_dv_per_position": h["dv_pm_24h"].mean(),
                    "mean_dv_per_position_abs_w_weighted": np.average(h["dv_pm_24h"], weights=h["w"].abs()),
                    "mean_daily_total_dv": h.groupby("day")["dv_pm_24h"].sum().mean(),
                    "median_dv_per_position": h["dv_pm_24h"].median()})
    pd.DataFrame(cap).to_csv(RES / "capacity.csv", index=False)

    # step 107: the claim, on log-odds y
    g1 = gaps[(gaps["comparison"] == "u minus E") & (gaps["target"] == "y")].iloc[0]
    s_b = sh[(sh.method == "msrr") & (sh.predictor == "Sbeta") & (sh.target == "y_money")].iloc[0]
    t_b = s_b["mean"] / (s_b["sd"] / np.sqrt(s_b["n_days"]))  # t-statistic of the average daily money return
    g3 = gaps[(gaps["comparison"] == "u: Polymarket minus stock")].iloc[0]
    claim = [("pure news Sharpe beats raw news", g1["gap"] > 0, f"gap {g1['gap']:.3f}, log-odds"),
             ("predictable news earns little (|t| of its average daily money return below 1.96)", abs(t_b) < 1.96,
              f"t {t_b:.2f}, money"),
             ("Polymarket Sharpe beats stock Sharpe on the same news", g3["gap"] > 0, f"gap {g3['gap']:.3f}")]
    out = ["# Test-period results (2026-08-28 to 2026-10-29)", "", "Daily Sharpe ratios, before trading costs.", "",
           "## Claim (step 107)", ""]
    out += [f"- {'HOLDS' if ok else 'FAILS'}: {t} ({n})" for t, ok, n in claim]
    out += ["", f"Overall: {'claim holds' if all(c[1] for c in claim) else 'claim does not hold'}.", ""]
    for title, t in [("Figure 4: out-of-sample Sharpe ratios by unit (step 95)", fig4.reset_index()),
                     ("Sharpe ratios (steps 93, 96, 97)", sh), ("Gaps of point Sharpe ratios (steps 96, 98)", gaps), ("R2 OOS of the ridge check (step 94)", r2.reset_index()),
                     ("Polymarket on stock (step 99)", pd.DataFrame(follow)),
                     ("Pure news, Polymarket money return on stock return (steps 100-102)", pure),
                     ("Volume terciles (step 104)", pd.DataFrame(ter)),
                     ("Flow regressions (step 105)", pd.DataFrame(flow)), ("Capacity (step 106)", pd.DataFrame(cap)),
                     ("Trade sizes (step 103, descriptive only)", pd.read_csv(RES / "trade_sizes.csv"))]:
        out += [f"## {title}", "", "```", t.to_string(index=False, float_format=lambda v: f"{v:.4g}"), "```", ""]
    (RES / "summary.md").write_text("\n".join(out))


if __name__ == "__main__":
    main()
