"""Step 85a: diagnostics of the standardized reaction xi on training days only (day < 2026-08-28, step 82).

    uv run python scripts/analysis/16_xi_diagnostics.py [--day midnight|close]

Reads data/news/xi_contracts.parquet (xi_contracts_close.parquet) from 13_reaction.py; test days are filtered at
read time and never loaded. One row per contract kind (close, barrier, all) x price bin of p0 x trading days left
(tau0 * 252) bin, plus the margins ("all"): n, mean xi (near 0 if fairly priced), mean xi^2 (= (true sigma / priced
sigma)^2, above 1 means Polymarket moves more than its prices imply), sd xi, and the OLS slope and R^2 of xi on
xi_hat_h20. Writes data/analysis/results/xi_diagnostics.csv and prints it.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RES = Path("data/analysis/results")
TRAIN_END = pd.Timestamp("2026-08-28")  # first test day (step 83); nothing on or after it is read
PBINS = [0, 0.05, 0.2, 0.5, 0.8, 0.95, 1.0]
DBINS = [0, 1, 5, 20, np.inf]


def stats(g):
    x, e = g["xi_hat_h20"].to_numpy(), g["xi"].to_numpy()
    xc = x - x.mean()
    slope = (xc * e).sum() / (xc ** 2).sum() if len(g) > 2 and (xc ** 2).sum() > 0 else np.nan
    r2 = slope ** 2 * (xc ** 2).sum() / ((e - e.mean()) ** 2).sum() if slope == slope else np.nan
    return {"n": len(g), "mean_xi": e.mean(), "mean_xi2": (e ** 2).mean(), "sd_xi": e.std(ddof=1) if len(g) > 1 else np.nan,
            "slope_on_xi_hat": slope, "r2_on_xi_hat": r2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", choices=["midnight", "close"], default="midnight")
    sfx = "_close" if ap.parse_args().day == "close" else ""
    x = pd.read_parquet(f"data/news/xi_contracts{sfx}.parquet", filters=[("day", "<", TRAIN_END)])
    assert x["day"].max() < TRAIN_END, "test days must not be read"
    x["group"] = np.where(x["kind"] == "close", "close", "barrier")
    x["p_bin"] = pd.cut(x["p0"], PBINS, labels=[f"{a:g}-{b:g}" for a, b in zip(PBINS[:-1], PBINS[1:])]).astype(str)
    x["days_bin"] = pd.cut(x["tau0"] * 252, DBINS, labels=["<=1", "2-5", "6-20", ">20"]).astype(str)
    rows = []
    for gr in ["close", "barrier", "all"]:
        for pb in ["all"] + sorted(x["p_bin"].unique()):
            for db in ["all", "<=1", "2-5", "6-20", ">20"]:
                m = ((x["group"] == gr) | (gr == "all")) & ((x["p_bin"] == pb) | (pb == "all")) & ((x["days_bin"] == db) | (db == "all"))
                if m.any():
                    rows.append({"group": gr, "p_bin": pb, "days_left": db, **stats(x[m])})
    res = pd.DataFrame(rows)
    RES.mkdir(parents=True, exist_ok=True)
    res.to_csv(RES / f"xi_diagnostics{sfx}.csv", index=False)
    print(res.to_string(index=False, float_format=lambda v: f"{v:.4g}"))


if __name__ == "__main__":
    main()
