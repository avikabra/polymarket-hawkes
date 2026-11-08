"""Steps 82 to 91: maximum Sharpe ratio regression (Kelly's MSRR), one fit per test day.

Joins data/news/news_shocks.parquet with data/news/reactions.parquet on (company_id, day)
(step 81) and, for each predictor X in {u, E, Sbeta, u_frozen, u_resid} and each target y:

  F_j(D) = sum_k X_j(k,D) y(k,D)                      daily factor returns (step 86)
  b(D)   = (F'F + lam I)^-1 F'1 over days < D          dual form F'(FF' + lam I)^-1 1 (step 87)
  w(k,D) = X(k,D) . b(D),  R(D) = sum_k w(k,D) y(k,D)  (steps 89, 92)

lam is picked once on the training days by leave-one-out (closed-form hat matrix, step 88).
u_resid (step 95a, last sentence): u with, on each day D, every coordinate regressed on [1, r_std_D_h20, r_std_Dm1_h20]
over company-days before D only (pooled OLS from running sums, 3x3 normal equations), the residual taken for day D;
days with fewer than MIN_FIT earlier company-days, or a missing control, drop out. Same targets as u_frozen; ridge check too.
Step 91 check: yhat = X.c by ridge on stacked company-days (re-fitted each test day, no
intercept), long the top fifth of yhat and short the bottom fifth each day.

Reactions columns used: company_id, day, y, y_money, y_stock, y_xi, xi_hat_h20, m_xi_h20, y_imp_h20, m_h20
(nullable). Optional: y_big, y_money_big (contracts with $10,000+ traded) and y_type_<name> (one contract type
alone); any such column present becomes an extra target (step 96). Targets run for u and E.

    uv run python scripts/analysis/14_msrr.py [--day midnight|close]

--day close (step 78g): reads reactions_close.parquet and joins the shock of calendar day D-1 to the reaction
of day D (the news for the window opening at the close of D is the articles dated D-1); outputs get a _close suffix.

Writes data/analysis/portfolio_returns.parquet (method, predictor, target, day, R),
data/analysis/test_weights.parquet (method, predictor, target, company_id, day, w, y) and
data/analysis/ridge_check.parquet (predictor, target, company_id, day, y, yhat), test days only. For
target y_xi, yhat is the out-of-sample prediction s_hat that 15_score.py (step 95a) uses.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

NEWS = Path("data/news")
OUT = Path("data/analysis")
TRAIN_END = pd.Timestamp("2026-08-27")   # step 82
TEST_START = pd.Timestamp("2026-08-28")  # step 83
TEST_END = pd.Timestamp("2026-10-29")
MAIN = ["y", "y_money", "y_same", "y_stock", "y_xi", "xi_hat_h20", "m_xi_h20", "y_imp_h20", "m_h20"]   # y_same = y on the y_stock company-days (step 97)
PREDICTORS = ["u", "E", "Sbeta", "u_frozen", "u_resid"]
MIN_FIT = 30  # earlier company-days needed before a residual is formed


def lam_grid(s):
    return s.max() * np.logspace(-8, 0, 17)


def loo_lambda(M, r):
    """Ridge of r on M; return the lam with the smallest leave-one-out squared error."""
    n, p = M.shape
    if n <= p:
        s, V = np.linalg.eigh(M @ M.T)
        s = np.clip(s, 0, None)
        proj = V.T @ r
        best = lambda lam: ((V ** 2) @ (s / (s + lam)), V @ (s / (s + lam) * proj))
    else:
        s, W = np.linalg.eigh(M.T @ M)
        s = np.clip(s, 0, None)
        Z = M @ W
        zr = Z.T @ r
        best = lambda lam: ((Z ** 2) @ (1 / (s + lam)), Z @ (zr / (s + lam)))
    grid = lam_grid(s)
    err = []
    for lam in grid:
        h, fit = best(lam)
        err.append(np.mean(((r - fit) / (1 - h)) ** 2))
    return grid[int(np.argmin(err))]


def msrr_weights(X, y, day, test_days):
    """Return per-row w for test rows, plus the daily factor matrix used."""
    days = np.unique(day)
    F = np.stack([X[day == d].T @ y[day == d] for d in days])  # days x 2560
    ok = days <= TRAIN_END
    lam = loo_lambda(F[ok].astype(np.float64), np.ones(ok.sum()))
    G = F.astype(np.float64) @ F.T.astype(np.float64)
    w = np.full(len(y), np.nan)
    for d in test_days:
        past = days < d  # steps 85, 89: only days whose 24 hours have passed
        rows = day == d
        if not rows.any() or past.sum() < 2:
            continue
        a = np.linalg.solve(G[np.ix_(past, past)] + lam * np.eye(past.sum()), np.ones(past.sum()))
        b = F[past].T.astype(np.float64) @ a
        w[rows] = X[rows] @ b
    return w


def ridge_check(X, y, day, test_days):
    """Step 91: yhat = X.c, c re-fitted each test day on all earlier company-days."""
    lam = loo_lambda(X[day <= TRAIN_END].astype(np.float64), y[day <= TRAIN_END].astype(np.float64))
    yhat = np.full(len(y), np.nan)
    days = np.unique(day)
    A = np.zeros((X.shape[1],) * 2)
    v = np.zeros(X.shape[1])
    done = 0
    for d in test_days:
        for e in days[done:]:  # fold in the days before d
            if e >= d:
                break
            Xe = X[day == e].astype(np.float64)
            A += Xe.T @ Xe
            v += Xe.T @ y[day == e]
            done += 1
        rows = day == d
        if rows.any():
            yhat[rows] = X[rows] @ np.linalg.solve(A + lam * np.eye(len(v)), v)
    return yhat


def residualize(U, Z, day):
    """Residual of each column of U on Z (rows = company-days) for each day, fitted on strictly earlier days only."""
    A, Bm, n = np.zeros((Z.shape[1],) * 2), np.zeros((Z.shape[1], U.shape[1])), 0
    out = np.full(U.shape, np.nan, np.float32)
    for d in np.unique(day):
        rows = day == d
        if n >= MIN_FIT:
            out[rows] = U[rows] - Z[rows] @ (np.linalg.pinv(A) @ Bm)
        A += Z[rows].T @ Z[rows]
        Bm += Z[rows].T @ U[rows]
        n += rows.sum()
    return out


def long_short(df):
    """Daily return of long top fifth / short bottom fifth by yhat."""
    out = {}
    for d, g in df.groupby("day"):
        q = len(g) // 5
        if q < 1:
            continue
        g = g.sort_values("yhat")
        out[d] = g["y"].iloc[-q:].mean() - g["y"].iloc[:q].mean()
    return pd.Series(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", choices=["midnight", "close"], default="midnight", help="step 78g day definition")
    close = ap.parse_args().day == "close"
    sfx = "_close" if close else ""
    OUT.mkdir(parents=True, exist_ok=True)
    rx = pd.read_parquet(NEWS / f"reactions{sfx}.parquet")
    rx["day"] = pd.to_datetime(rx["day"]).dt.normalize()
    rx["y_same"] = rx["y"].where(rx["y_stock"].notna())
    extra = [c for c in rx.columns if c in ("y_big", "y_money_big") or c.startswith("y_type_")]
    targets = MAIN + extra
    rets, weights, checks = [], [], []
    for pred in PREDICTORS:
        sh = pd.read_parquet(NEWS / "news_shocks.parquet", columns=["company_id", "day", "u" if pred == "u_resid" else pred]).rename(columns={"u": pred})
        sh["day"] = pd.to_datetime(sh["day"]).dt.normalize() + pd.Timedelta(days=int(close))  # close: shock of D-1 meets reaction of D
        df = sh.merge(rx, on=["company_id", "day"])  # step 81: shock and y both present
        df = df[df["day"] <= TEST_END].reset_index(drop=True)
        if pred == "u_resid":
            df = df.dropna(subset=["r_std_D_h20", "r_std_Dm1_h20"]).sort_values("day", kind="stable").reset_index(drop=True)
        Xall = np.stack(df[pred].to_numpy()).astype(np.float32)
        if pred == "u_resid":
            Xall = residualize(Xall, np.c_[np.ones(len(df)), df[["r_std_D_h20", "r_std_Dm1_h20"]].to_numpy()], df["day"].to_numpy())
            keep = ~np.isnan(Xall[:, 0])
            df, Xall = df[keep].reset_index(drop=True), Xall[keep]
        test_days = np.sort(df.loc[df["day"] >= TEST_START, "day"].unique())
        for tgt in targets:
            if tgt not in MAIN and pred not in ("u", "E"):
                continue
            m = df[tgt].notna().to_numpy()
            X, y, day = Xall[m], df.loc[m, tgt].to_numpy(np.float64), df.loc[m, "day"].to_numpy()
            w = msrr_weights(X, y, day, test_days)
            t = pd.DataFrame({"company_id": df.loc[m, "company_id"].to_numpy(), "day": day, "w": w, "y": y})
            t = t[t["w"].notna()]
            t.insert(0, "target", tgt)
            t.insert(0, "predictor", pred)
            t.insert(0, "method", "msrr")
            weights.append(t)
            R = (t["w"] * t["y"]).groupby(t["day"]).sum()
            rets.append(R.rename("R").reset_index().assign(method="msrr", predictor=pred, target=tgt))
            print(pred, tgt, "test days", len(R), flush=True)
        if pred in ("u", "E", "Sbeta", "u_resid"):  # step 91 check, on y and on y_xi (yhat of y_xi = s_hat, step 95a)
            for tgt in ("y", "y_xi"):
                m = df[tgt].notna().to_numpy()
                X, y, day = Xall[m], df.loc[m, tgt].to_numpy(np.float64), df.loc[m, "day"].to_numpy()
                yh = ridge_check(X, y, day, test_days)
                c = pd.DataFrame({"predictor": pred, "target": tgt, "company_id": df.loc[m, "company_id"].to_numpy(),
                                  "day": day, "y": y, "yhat": yh}).dropna(subset=["yhat"])
                checks.append(c)
                R = long_short(c)
                rets.append(R.rename("R").rename_axis("day").reset_index().assign(method="ridge", predictor=pred, target=tgt))
        del Xall, df
    pd.concat(rets).to_parquet(OUT / f"portfolio_returns{sfx}.parquet", index=False)
    pd.concat(weights).to_parquet(OUT / f"test_weights{sfx}.parquet", index=False)
    pd.concat(checks).to_parquet(OUT / f"ridge_check{sfx}.parquet", index=False)


if __name__ == "__main__":
    main()
