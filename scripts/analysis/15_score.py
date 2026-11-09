"""Steps 92 to 107: score the test-period portfolios from 14_msrr.py. Run once, after every choice is locked.

Inputs: data/analysis/{portfolio_returns,test_weights,ridge_check}.parquet from 14_msrr.py,
data/news/reactions.parquet (needs company_id, day, y, y_money, y_stock, y_xi, xi_hat_h*, m_xi_h*, r_std_D_h*,
r_std_Dm1_h*, g0_h*, dv_pm_24h, flow_small, flow_large), data/news/xi_contracts.parquet and data/stocks/prices.parquet
(step 95a resampling) and the trade files under data/polymarket/trades (size_usdc, for step 103).

    uv run python scripts/analysis/15_score.py [--day midnight|close]

Writes data/analysis/results/*.csv and summary.md (results_close/ and _close inputs with --day close). All Sharpe
ratios are per day, before costs. Step 95a (reaction_regressions.csv, reaction_beta_check.csv): on test
company-days, T = alpha_D + beta s_hat + d1 r_std_D + d2 r_std_Dm1 + d3 g0 for T in y_xi, xi_hat, m_xi, and
y_xi = alpha_D + beta s_hat + gamma xi_hat + d X, s_hat = the out-of-sample ridge prediction of y_xi from u
(14_msrr.py), held fixed in every resample. Bootstrap: 10,000 draws of day counts n_j, multinomial over all NYSE
sessions through the test end; sigma is recomputed as the count-weighted EWMA
sigma2_D = sum_j lam^(D-j) n_j r_j^2 / sum_j lam^(D-j) n_j, then xi_hat, m_xi, g0 (from the contract file) and
r_std, and the regressions are re-run weighted by n (a company-day takes the count of the last session <= D).
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

A = Path("data/analysis")
TEST_START = pd.Timestamp("2026-08-28")
TEST_END = pd.Timestamp("2026-10-29")
B = 10_000
CH = 100  # draws per chunk
rng = np.random.default_rng(0)


def sharpe(x):
    return x.mean() / x.std(ddof=1)


UNIT = {"y": "log-odds (step 74)", "y_same": "log-odds (step 74)", "y_big": "log-odds (step 74)",
        "y_money": "money (step 77)", "y_money_big": "money (step 77)", "y_stock": "stock return (step 78)",
        "y_xi": "xi (step 78c)", "xi_hat_h20": "xi (step 78d)", "m_xi_h20": "xi (step 78e)",
        "y_imp_h20": "log-odds (step 74)", "m_h20": "log-odds (step 74)"}


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


# step 95a: Z columns are s_hat, r_D, r_Dm1, g0, xi_hat, y_xi, m_xi
SPECS = {("A", "y_xi"): ([0, 1, 2, 3], 5), ("A", "xi_hat"): ([0, 1, 2, 3], 4), ("A", "m_xi"): ([0, 1, 2, 3], 6),
         ("B", "y_xi"): ([0, 4, 1, 2, 3], 5)}  # B: gamma on xi_hat free
TERMS = {"A": ["beta", "delta1", "delta2", "delta3"], "B": ["beta", "gamma", "delta1", "delta2", "delta3"]}


def fe_wls(Z, w, ind):
    """Z (b,R,7), weights w (b,R), ind (R,days) one-hot. Weighted within-day demeaning (day fixed effects), then
    weighted least squares per spec. Returns ({spec: coefficients (b,k)}, demeaned Z). Non-finite rows get weight 0."""
    ok = np.isfinite(Z).all(-1)
    Z, w = np.where(ok[..., None], Z, 0.0), np.where(ok, w, 0.0)
    den = np.einsum("br,rd->bd", w, ind)
    mean = np.einsum("brj,rd->bdj", Z * w[..., None], ind) / np.where(den > 0, den, 1)[..., None]
    Z = Z - np.einsum("bdj,rd->brj", mean, ind)
    out = {}
    for sp, (xc, yc) in SPECS.items():
        X, y = Z[:, :, xc], Z[:, :, yc]
        out[sp] = np.einsum("bkl,bl->bk", np.linalg.pinv(np.einsum("brk,br,brl->bkl", X, w, X)), np.einsum("brk,br,br->bk", X, w, y))
    return out, Z


def cluster_se(X, y, beta, cl, extra):
    """CR1 standard errors: G/(G-1) (N-1)/(N-K), K = regressors + `extra` absorbed day effects not nested in the clusters."""
    e = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    sc = pd.DataFrame(X * e[:, None]).groupby(cl).sum().to_numpy()
    G, N, K = len(sc), len(y), X.shape[1] + extra
    return np.sqrt(np.diag(bread @ (sc.T @ sc) @ bread * G / (G - 1) * (N - 1) / (N - K)))


def ewma_sd(n, R2, M, ok, lam, t_lo):
    """Daily count-weighted EWMA sd at sessions t_lo.. for every draw: (draws, sessions, companies)."""
    A = np.zeros((n.shape[0], R2.shape[1]))
    Dn = A.copy()
    out = []
    for t in range(len(R2)):
        A, Dn = lam * A + n[:, t, None] * R2[t], lam * Dn + n[:, t, None] * M[t]
        if t >= t_lo:
            with np.errstate(all="ignore"):
                out.append(np.where(ok[t], np.sqrt(A / Dn), np.nan))
    return np.stack(out, 1)


def reaction_regressions(rx, ck, ct, px, mod):
    """Step 95a for each half-life: point estimates with company and day clustered SEs, and bootstrap intervals."""
    sh = ck[(ck["predictor"] == "u") & (ck["target"] == "y_xi")][["company_id", "day", "yhat"]].rename(columns={"yhat": "s_hat"})
    rx = rx[(rx["day"] >= TEST_START) & (rx["day"] <= TEST_END)].merge(sh, on=["company_id", "day"])
    px = px.dropna().drop_duplicates(["company_id", "date"]).sort_values(["company_id", "date"])
    px["r"] = np.log(px["adj_close"]).groupby(px["company_id"]).diff()
    sess = pd.DatetimeIndex(np.sort(px.loc[px["company_id"] == "spy", "date"].unique()))
    sess = sess[sess <= TEST_END]
    Rm = px.pivot(index="date", columns="company_id", values="r").reindex(sess)
    comps, Rr = list(Rm.columns), Rm.to_numpy()
    M = np.isfinite(Rr)
    R2, ok20 = np.where(M, Rr, 0.0) ** 2, np.cumsum(M, 0) >= 20  # sigma needs 20 returns, as in 13_reaction.py
    rows, betas = [], []
    for h in (20, 10, 60):
        d = rx.dropna(subset=["s_hat", "y_xi"] + [f"{a}_h{h}" for a in ("xi_hat", "m_xi", "r_std_D", "r_std_Dm1", "g0")]).reset_index(drop=True)
        d["g"] = np.arange(len(d))
        i = sess.searchsorted(d["day"], "right") - 1  # last session <= D
        c = np.array([comps.index(x) for x in d["company_id"]])
        dcode, ccode = pd.factorize(d["day"])[0], pd.factorize(d["company_id"])[0]
        ind = (dcode[:, None] == np.arange(dcode.max() + 1)).astype(float)
        base = [d["s_hat"], d[f"r_std_D_h{h}"], d[f"r_std_Dm1_h{h}"], d[f"g0_h{h}"], d[f"xi_hat_h{h}"], d["y_xi"], d[f"m_xi_h{h}"]]
        coef, Zt = fe_wls(np.stack(base, -1)[None], np.ones((1, len(d))), ind)
        for (sp, tg), (xc, yc) in SPECS.items():
            X, y, be = Zt[0][:, xc], Zt[0][:, yc], coef[sp, tg][0]
            se_c, se_d = cluster_se(X, y, be, ccode, ind.shape[1]), cluster_se(X, y, be, dcode, 0)
            for j, term in enumerate(TERMS[sp]):
                rows.append({"half_life": h, "spec": sp, "target": tg, "term": term, "est": be[j], "se_company": se_c[j], "se_day": se_d[j],
                             "n_obs": len(d), "n_days": ind.shape[1], "n_companies": ccode.max() + 1})
        # contracts of these company-days, grouped in row order
        k = ct.merge(d[["company_id", "day", "g"]], on=["company_id", "day"]).sort_values("g")
        starts = np.flatnonzero(np.r_[True, k["g"].to_numpy()[1:] != k["g"].to_numpy()[:-1]])
        assert len(starts) == len(d)
        w, g = k["weight"].to_numpy(), k["g"].to_numpy()
        kind, sgn = k["kind"].to_numpy(), np.where(k["kind"].to_numpy() == "up", -1.0, 1.0)
        S0, S1, K, z0 = (k[x].to_numpy(float) for x in ("S0", "S1", "strike", "z0"))
        r0, r1, rd = (np.sqrt(k[x].to_numpy(float)) for x in ("tau0", "tau1", "dt"))
        wsum = np.add.reduceat(w, starts)
        t_lo, T = max(int(i.min()) - 2, 0), len(sess)
        rr, rr1, ydat = Rr[i, c], Rr[i - 1, c], d["y_xi"].to_numpy()
        gen = np.random.default_rng(1)
        draws = []
        for _ in range(B // CH):
            n = gen.multinomial(T, np.full(T, 1 / T), size=CH)  # day counts n_j over all sessions through the test end
            sd = ewma_sd(n, R2, M, ok20, 0.5 ** (1 / h), t_lo)  # daily scale, (draws, sessions from t_lo, companies)
            sig = sd[:, i[g] - t_lo, c[g]] * np.sqrt(252)
            zh0, zh1 = mod.model(S0, K, sig, r0 ** 2, kind)[1], mod.model(S1, K, sig, r1 ** 2, kind)[1]
            xh = np.add.reduceat(w * sgn * (zh1 * r1 - zh0 * r0) / rd, starts, axis=1) / wsum
            g0 = np.add.reduceat(w * sgn * (z0 - zh0) * r0 / rd, starts, axis=1) / wsum
            Z = np.stack([np.broadcast_to(d["s_hat"].to_numpy(), xh.shape), rr / sd[:, i - 1 - t_lo, c],  # sd through D-1
                          rr1 / sd[:, i - 2 - t_lo, c], g0, xh, np.broadcast_to(ydat, xh.shape), ydat - xh], -1)
            cf, _ = fe_wls(Z, n[:, i].astype(float), ind)
            draws.append(cf)
        for r_ in rows:
            if r_["half_life"] == h:
                bs = np.concatenate([x[r_["spec"], r_["target"]] for x in draws])[:, TERMS[r_["spec"]].index(r_["term"])]
                r_["boot_lo"], r_["boot_hi"] = np.percentile(bs, [2.5, 97.5])
    res = pd.DataFrame(rows)
    a = res[(res["spec"] == "A") & (res["term"] == "beta")].pivot(index="half_life", columns="target", values="est")
    chk = pd.DataFrame({"beta_y_xi": a["y_xi"], "beta_xi_hat_plus_beta_m_xi": a["xi_hat"] + a["m_xi"], "diff": a["y_xi"] - a["xi_hat"] - a["m_xi"]}).reset_index()
    return res, chk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", choices=["midnight", "close"], default="midnight", help="step 78g day definition")
    sfx = "_close" if ap.parse_args().day == "close" else ""
    RES = A / f"results{sfx}"
    RES.mkdir(parents=True, exist_ok=True)
    pr = pd.read_parquet(A / f"portfolio_returns{sfx}.parquet")
    pr = pr[pr["day"] >= TEST_START]
    W = pd.read_parquet(A / f"test_weights{sfx}.parquet")
    rx = pd.read_parquet(f"data/news/reactions{sfx}.parquet")
    rx["day"] = pd.to_datetime(rx["day"]).dt.normalize()
    R = {k: g.set_index("day")["R"] for k, g in pr.groupby(["method", "predictor", "target"])}

    # steps 93, 96, 97: Sharpe of every portfolio, each labelled with its unit
    rows = [sharpe_row(s, method=k[0], predictor=k[1], target=k[2], unit=unit(k[2])) for k, s in R.items()]
    sh = pd.DataFrame(rows)
    sh.to_csv(RES / "sharpe.csv", index=False)
    # step 95: Kelly et al. Figure 4, news shock vs raw news vs predictable news, in xi (the headline, slide 15), money and log-odds
    fig4 = sh[(sh.method == "msrr") & sh.predictor.isin(["u", "E", "Sbeta", "u_resid"]) & sh.target.isin(["y_xi", "y_money", "y"])] \
        .pivot(index="predictor", columns="unit", values="sharpe").reindex(["u", "E", "Sbeta", "u_resid"])
    fig4.index = fig4.index.map({"u": "news shock (u)", "E": "raw news (E)", "Sbeta": "predictable news (S beta)",
                                 "u_resid": "news shock residualized on stock returns (u_resid, step 95a)"})
    fig4.reset_index().to_csv(RES / "figure4_sharpe.csv", index=False)

    # steps 96, 98: gaps of the point Sharpe ratios, pure news minus raw news (each target) and Polymarket minus stock
    gaps = []
    for t in sorted({k[2] for k in R if k[0] == "msrr"}):
        if ("msrr", "u", t) in R and ("msrr", "E", t) in R:
            gaps.append(gap_row(R["msrr", "u", t], R["msrr", "E", t], comparison="u minus E", target=t))
    for p in ["u", "E", "Sbeta", "u_frozen", "u_resid"]:
        if ("msrr", p, "y_same") in R and ("msrr", p, "y_stock") in R:
            gaps.append(gap_row(R["msrr", p, "y_same"], R["msrr", p, "y_stock"], comparison=f"{p}: Polymarket minus stock", target="y_same vs y_stock"))
    gaps = pd.DataFrame(gaps)
    gaps.to_csv(RES / "gaps.csv", index=False)

    # step 94: R2_OOS of the ridge check
    ck = pd.read_parquet(A / f"ridge_check{sfx}.parquet")
    r2 = ck.groupby(["predictor", "target"]).apply(lambda g: pd.Series({
        "r2_oos": 1 - ((g["y"] - g["yhat"]) ** 2).sum() / (g["y"] ** 2).sum(), "n": len(g)}), include_groups=False)
    r2.reset_index().to_csv(RES / "r2_oos.csv", index=False)

    # step 99: y = a + c * (stock return in %), all test company-days; y_xi on r_win (the window's standardized stock return), where an efficient close contract has c = 1
    d = rx[rx["day"] >= TEST_START].dropna(subset=["y", "y_stock"])
    follow = [{"sample": "y on stock return %", **ols(100 * d["y_stock"], d["y"], d["day"])}]
    for h in (20, 10, 60):
        d = rx[rx["day"] >= TEST_START].dropna(subset=["y_xi", f"r_win_h{h}"])
        f = ols(d[f"r_win_h{h}"], d["y_xi"], d["day"])  # the stock's standardized return over the same window
        follow.append({"sample": f"y_xi on r_win, half-life {h}", **f, "t_vs_1": (f["c"] - 1) / f["se"]})
    pd.DataFrame(follow).to_csv(RES / "stock_follow.csv", index=False)

    # step 95a: reaction regressions on s_hat, with bootstrap over test days through the whole pipeline
    spec = importlib.util.spec_from_file_location("reaction13", Path(__file__).resolve().parents[1] / "ingest" / "13_reaction.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ct = pd.read_parquet(f"data/news/xi_contracts{sfx}.parquet", filters=[("day", ">=", TEST_START)])
    ct["day"] = ct["day"].astype("datetime64[ns]")
    px = pd.read_parquet("data/stocks/prices.parquet", columns=["company_id", "date", "adj_close"])
    px["date"] = pd.to_datetime(px["date"]).astype("datetime64[ns]")
    reg, chk = reaction_regressions(rx, ck, ct, px, mod)
    reg.to_csv(RES / "reaction_regressions.csv", index=False)
    chk.to_csv(RES / "reaction_beta_check.csv", index=False)

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
                     ("Reaction regressions on s_hat (step 95a); bootstrap holds s_hat fixed", reg),
                     ("beta(y_xi) against beta(xi_hat) + beta(m_xi) (step 95a)", chk),
                     ("Pure news, Polymarket money return on stock return (steps 100-102)", pure),
                     ("Volume terciles (step 104)", pd.DataFrame(ter)),
                     ("Flow regressions (step 105)", pd.DataFrame(flow)), ("Capacity (step 106)", pd.DataFrame(cap)),
                     ("Trade sizes (step 103, descriptive only)", pd.read_csv(RES / "trade_sizes.csv"))]:
        out += [f"## {title}", "", "```", t.to_string(index=False, float_format=lambda v: f"{v:.4g}"), "```", ""]
    (RES / "summary.md").write_text("\n".join(out))


if __name__ == "__main__":
    main()
