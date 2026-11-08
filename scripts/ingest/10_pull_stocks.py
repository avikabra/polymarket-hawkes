"""Steps 45, 70 and 71: Yahoo Finance prices, T-bill rate, TWD rate and statements for the 61 companies.

Runs on Bouchet only; never run it on a laptop. One part file per ticker is written first, so a
stopped job resumes and skips every ticker already on disk.

    uv run python scripts/ingest/10_pull_stocks.py

Writes under data/stocks/:
  prices.parquet      company_id ("spy" for the S&P 500 fund), date, close, adj_close, volume
                      (close is split-adjusted, adj_close also carries dividends)
  rf.parquet          date, rf_daily = ^IRX / 100 / 12 / 21 (3-month T-bill, step 45)
  fx.parquet          date, twd_per_usd = Yahoo "TWD=X" close (Taiwan dollars per US dollar, for TSMC, step 70)
  statements.parquet  company_id, period_end, freq (annual|quarterly), then the step 71 fields,
                      then financial_currency (Yahoo's reporting currency; 11 converts non-USD, step 49)
  coverage.csv        per company and freq: periods and non-missing count of each field, plus
                      Yahoo's financial currency
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import yfinance as yf

from src.ingest.companies import load_companies
from src.utils import get_logger

log = get_logger(__name__)
OUT = Path("data/stocks")
PARTS = OUT / "_parts"
START, END = "2020-09-01", "2026-10-31"  # Yahoo's end date is exclusive
SLEEP = 2.0
NO_STMT = ("spy", "irx", "twd")  # series pulled for prices only

# our field -> Yahoo row names, first one present wins
FIELDS = {
    "revenue": ["TotalRevenue", "OperatingRevenue"],
    "ebitda": ["EBITDA", "NormalizedEBITDA"],
    "operating_expenses": ["OperatingExpense", "TotalExpenses"],
    "gross_profit": ["GrossProfit"],
    "sga": ["SellingGeneralAndAdministration"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonOperating"],
    "shareholders_equity": ["StockholdersEquity"],
    "common_equity": ["CommonStockEquity"],
    "preferred_stock": ["PreferredStock", "PreferredStockEquity"],
    "deferred_taxes": ["NonCurrentDeferredTaxesLiabilities", "DeferredTax"],
    "total_assets": ["TotalAssets"],
    "total_liabilities": ["TotalLiabilitiesNetMinorityInterest"],
}


def pull_prices(ticker: str) -> pd.DataFrame:
    h = yf.Ticker(ticker).history(start=START, end=END, interval="1d", auto_adjust=False)
    if h.empty:
        return pd.DataFrame(columns=["date", "close", "adj_close", "volume"])
    out = pd.DataFrame({"date": h.index.tz_localize(None).normalize(), "close": h["Close"].values,
                        "adj_close": h["Adj Close"].values, "volume": h["Volume"].values})
    return out.dropna(subset=["close"])


def pull_statements(company_id: str, ticker: str) -> pd.DataFrame:
    t, rows = yf.Ticker(ticker), []
    for freq, yf_freq in (("annual", "yearly"), ("quarterly", "quarterly")):
        frames = [t.get_income_stmt(freq=yf_freq), t.get_balance_sheet(freq=yf_freq)]
        raw = pd.concat([f for f in frames if f is not None and not f.empty])
        if raw.empty:
            continue
        raw = raw[~raw.index.duplicated()].T
        out = pd.DataFrame({"company_id": company_id, "period_end": pd.to_datetime(raw.index), "freq": freq})
        for field, names in FIELDS.items():
            have = [n for n in names if n in raw.columns]
            out[field] = raw[have].bfill(axis=1).iloc[:, 0].astype(float).values if have else float("nan")
        rows.append(out)
    return pd.concat(rows) if rows else pd.DataFrame()


def main() -> None:
    PARTS.mkdir(parents=True, exist_ok=True)
    companies = load_companies()
    todo = [("spy", "SPY"), ("irx", "^IRX"), ("twd", "TWD=X")] + [(c.id, c.ticker) for c in companies]
    for cid, ticker in todo:
        p_price, p_stmt = PARTS / f"{cid}_prices.parquet", PARTS / f"{cid}_statements.parquet"
        if p_price.exists() and (p_stmt.exists() or cid in NO_STMT):
            continue
        try:
            pull_prices(ticker).to_parquet(p_price, index=False)
            if cid not in NO_STMT:
                st = pull_statements(cid, ticker)
                cur = None
                try:
                    cur = yf.Ticker(ticker).get_info().get("financialCurrency")
                except Exception:
                    pass
                st.assign(financial_currency=cur).to_parquet(p_stmt, index=False)
            log.info("pulled", company=cid, ticker=ticker)
        except Exception as e:  # leave the part missing so the next run retries it
            log.warning("pull failed", company=cid, ticker=ticker, error=str(e))
        time.sleep(SLEEP)

    px = [pd.read_parquet(PARTS / f"{cid}_prices.parquet").assign(company_id=cid)
          for cid, _ in todo if (PARTS / f"{cid}_prices.parquet").exists()]
    allpx = pd.concat(px)
    irx = allpx[allpx["company_id"] == "irx"]
    rf = pd.DataFrame({"date": irx["date"], "rf_daily": irx["close"] / 100 / 12 / 21}).dropna()
    rf.to_parquet(OUT / "rf.parquet", index=False)
    twd = allpx[allpx["company_id"] == "twd"]
    pd.DataFrame({"date": twd["date"], "twd_per_usd": twd["close"]}).dropna().to_parquet(OUT / "fx.parquet", index=False)
    allpx[~allpx["company_id"].isin(["irx", "twd"])][["company_id", "date", "close", "adj_close", "volume"]] \
        .to_parquet(OUT / "prices.parquet", index=False)

    st = [pd.read_parquet(p) for p in sorted(PARTS.glob("*_statements.parquet"))]
    st = pd.concat([s for s in st if len(s)]) if st else pd.DataFrame()
    cur = st.groupby("company_id")["financial_currency"].first() if len(st) else pd.Series(dtype=object)
    st.to_parquet(OUT / "statements.parquet", index=False)

    # coverage: how many periods each company has per freq, and how many of them carry each field
    cov = []
    for c in companies:
        for freq in ("annual", "quarterly"):
            s = st[(st["company_id"] == c.id) & (st["freq"] == freq)] if len(st) else st
            row = {"company_id": c.id, "freq": freq, "periods": len(s), "financial_currency": cur.get(c.id)}
            row.update({f: int(s[f].notna().sum()) if len(s) else 0 for f in FIELDS})
            cov.append(row)
    pd.DataFrame(cov).to_csv(OUT / "coverage.csv", index=False)
    log.info("done", prices=len(allpx), statements=len(st))


if __name__ == "__main__":
    main()
