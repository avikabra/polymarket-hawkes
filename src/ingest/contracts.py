"""Polymarket contracts: pull_plan steps 3 to 11.

One event is one contract group; its markets are the rungs. Every rung keeps a row, and
`excluded_reason` records why a rung left (null means kept), so the pull report can count
every exclusion. A rung leaves only for a reason known when it opens (type, scheduled life,
readable strike, scheduled end inside the window); nothing read from an outcome or a
settlement time excludes it. The ladder and close checks read outcomes, so they are report-only.
Entry point: scripts/ingest/02_pull_contracts.py.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.ingest.companies import Company
from src.polymarket.gamma import GammaClient

ET = "America/New_York"

# ── step 4: type from Polymarket's type tags, first match wins ────────────────
EARNINGS, KPI, VALUATION = "earnings", "kpi", "valuation"
BARRIER_LADDER, CLOSE_LADDER, CLOSE_BUCKET, UP_DOWN = (
    "barrier_ladder", "close_ladder", "close_bucket", "up_or_down")

# Tag labels as Polymarket spells them. Most close ladders carry "Multi Strikes". Daily and
# older close ladders carry only "Daily-Close" or "Stock Prices"; daily up/down markets carry
# those tags too, so they rank after "Up or Down".
TYPE_TAGS: list[tuple[str, set[str]]] = [
    (EARNINGS, {"Earnings"}),
    (KPI, {"KPIs", "KPI"}),
    (VALUATION, {"market cap", "market caps", "market capitalization", "IPO", "IPOs"}),
    (BARRIER_LADDER, {"Hit Price", "Monthly Hit", "Yearly Hit"}),
    (CLOSE_LADDER, {"Multi Strikes"}),
    (UP_DOWN, {"Up or Down"}),
    (CLOSE_LADDER, {"Daily-Close", "Stock Prices"}),
]
STRIKE_TYPES = {KPI, VALUATION, BARRIER_LADDER, CLOSE_LADDER, CLOSE_BUCKET}
PRICE_STRIKE_TYPES = {BARRIER_LADDER, CLOSE_LADDER, CLOSE_BUCKET}


def contract_type(tag_labels: list[str], neg_risk: bool) -> str | None:
    labels = set(tag_labels)
    for typ, tags in TYPE_TAGS:
        if labels & tags:
            # a ladder of mutually exclusive price ranges is a closing bucket, whichever tag it carries
            return CLOSE_BUCKET if typ in (CLOSE_LADDER, BARRIER_LADDER) and neg_risk else typ
    return None


# ── steps 7 and 8: strike and direction ───────────────────────────────────────
_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_MULT = {"": 1.0, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}


def _val(x: str, suffix: str) -> float:
    return float(x.replace(",", "")) * _MULT[suffix.lower()]


@dataclass(frozen=True)
class Strike:
    lo: float | None
    hi: float | None
    direction: str | None  # above | below | bucket | None (bare price: read the question)
    fmt: str               # arrow | cmp | range | plus | bare | empty | unparsed


def parse_label(label: str | None) -> Strike:
    """Strike and, where the label shows it, direction from `groupItemTitle`."""
    s = (label or "").strip()
    if not s:
        return Strike(None, None, None, "empty")
    m = re.fullmatch(r"([↑↓])\s*\$?" + _NUM + r"\s*([kmbt]?)\s*%?", s, re.I)
    if m:
        return Strike(_val(m[2], m[3]), None, "above" if m[1] == "↑" else "below", "arrow")
    m = re.fullmatch(r"([<>≥≤]=?)\s*\$?" + _NUM + r"\s*([kmbt]?)\s*%?", s, re.I)
    if m:
        return Strike(_val(m[2], m[3]), None, "above" if m[1][0] in ">≥" else "below", "cmp")
    m = re.fullmatch(r"\$?" + _NUM + r"\s*([kmbt]?)\s*%?\s*(?:[-–]|to)\s*\$?" + _NUM + r"\s*([kmbt]?)\s*%?", s, re.I)
    if m:
        hi_suf = m[4] or ""
        return Strike(_val(m[1], m[2] or hi_suf), _val(m[3], hi_suf), "bucket", "range")
    m = re.fullmatch(r"\$?" + _NUM + r"\s*([kmbt]?)\s*%?\+", s, re.I)
    if m:
        return Strike(_val(m[1], m[2]), None, "above", "plus")
    m = re.fullmatch(r"\$?" + _NUM + r"\s*([kmbt]?)\s*%?", s, re.I)
    if m:
        return Strike(_val(m[1], m[2]), None, None, "bare")
    return Strike(None, None, None, "unparsed")


def question_direction(question: str | None) -> str | None:
    """Direction of a bare-price rung from its question ("Will Apple close above $250?")."""
    q = (question or "").lower()
    if re.search(r"\b(dip|low)\b|\(low\)", q):
        return "below"
    if re.search(r"\b(above|over|exceed|greater than|at least|more than|higher than|hit|reach)\b|\(high\)", q):
        return "above"
    if re.search(r"\b(below|under|less than|fewer than|lower than)\b", q):
        return "below"
    return None


# ── helpers ───────────────────────────────────────────────────────────────────
def to_utc(value) -> pd.Timestamp | None:
    if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
        return None
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _json_list(x) -> list:
    return json.loads(x) if isinstance(x, str) else list(x or [])


def outcome_yes(outcome_prices, outcomes) -> int | None:
    """1 if YES won, 0 if NO won, None if unresolved, voided or split."""
    try:
        prices = [float(p) for p in _json_list(outcome_prices)]
        labels = [str(o).lower() for o in _json_list(outcomes)]
        y = prices[labels.index("yes")] if "yes" in labels else prices[0]
    except (TypeError, ValueError, IndexError):
        return None
    return 1 if y > 0.99 else 0 if y < 0.01 else None


def token_ids(clob_token_ids, outcomes) -> tuple[str | None, str | None]:
    """(YES-side token, NO-side token). Up/down markets list "Up" first."""
    try:
        ids = _json_list(clob_token_ids)
        labels = [str(o).lower() for o in _json_list(outcomes)]
        i = labels.index("yes") if "yes" in labels else 0
        return str(ids[i]), str(ids[1 - i])
    except (TypeError, ValueError, IndexError):
        return None, None


# ── step 3: pull ──────────────────────────────────────────────────────────────
async def pull_events(client: GammaClient, companies: list[Company], end_max: str) -> list[dict]:
    """Every closed event carrying each company's ticker tag, ending on or before `end_max`."""
    stop = (pd.Timestamp(end_max) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    out = []
    for c in companies:
        for ev in await client.tag_events(c.polymarket_tag_id, end_date_max=stop):
            out.append({**ev, "_company_id": c.id})
    return out


# ── steps 4 to 8 and 11: one row per rung ─────────────────────────────────────
def exclusion_reason(r, end_max) -> str | None:
    # Every test reads only what is known when the rung opens: tags, label, question and
    # scheduled dates. The settlement time (end_ts_utc) and the outcome are never read.
    if pd.isna(r.scheduled_end_ts_utc) or pd.isna(r.start_et):
        return "missing_dates"
    if r.scheduled_end_ts_utc.tz_convert(ET).date() > end_max:
        return "ends_after_window"
    if r.contract_type is None:
        return "no_financial_type_tag"                       # step 4
    if (r.scheduled_end_ts_utc - r.start_ts_utc) < pd.Timedelta(hours=24):
        return "open_under_24h"                              # step 5
    if (r.scheduled_end_ts_utc - r.start_ts_utc) < pd.Timedelta(hours=48):
        # daily contracts list around noon and resolve at the next close (about 32 hours),
        # so an article GDELT dates to a day has no full day of trading after it
        return "daily_contract"                              # step 5
    if r.contract_type in STRIKE_TYPES and pd.isna(r.strike_lo):
        return "strike_unreadable"                           # step 7
    if r.contract_type in STRIKE_TYPES and r.direction is None:
        return "direction_unreadable"                        # step 8
    return None


def exclusion_reasons(mk: pd.DataFrame, end_max) -> list[str | None]:
    return [exclusion_reason(r, end_max) for r in mk.itertuples()]


def build_markets(events: list[dict], cfg: dict) -> pd.DataFrame:
    end_max = pd.Timestamp(cfg["end_max"]).date()
    rows, seen = [], set()
    for ev in events:
        eid = str(ev["id"])
        if eid in seen:
            continue
        seen.add(eid)
        labels = [t.get("label") for t in ev.get("tags") or []]
        neg = bool(ev.get("negRisk"))
        ctype = contract_type(labels, neg)
        for m in ev.get("markets") or []:
            st = parse_label(m.get("groupItemTitle"))
            direction = st.direction or (question_direction(m.get("question")) if st.fmt == "bare" else None)
            if ctype in (EARNINGS, UP_DOWN):
                st, direction = Strike(None, None, None, "none"), None
            elif neg and ctype in STRIKE_TYPES and st.fmt in ("cmp", "plus"):
                # open-ended end buckets: "<$240" is [0, 240), ">$260" and "$260+" are [260, inf)
                st = Strike(0.0, st.lo, "bucket", st.fmt) if direction == "below" else Strike(st.lo, None, "bucket", st.fmt)
                direction = "bucket"
            start = to_utc(m.get("acceptingOrdersTimestamp")) or to_utc(m.get("startDate")) or to_utc(ev.get("startDate"))
            sched_end = to_utc(m.get("endDate")) or to_utc(ev.get("endDate"))
            settled = to_utc(m.get("closedTime"))
            end = sched_end  # actual end: when the contract stopped trading, never a filter
            if ctype == BARRIER_LADDER and settled is not None and sched_end is not None and settled < sched_end:
                end = settled  # a touched strike ends the question
            yes_tok, no_tok = token_ids(m.get("clobTokenIds"), m.get("outcomes"))
            rows.append({
                "market_id": str(m["id"]), "condition_id": m.get("conditionId"), "event_id": eid,
                "company_id": ev["_company_id"], "event_title": ev.get("title"),
                "question": m.get("question"), "label": m.get("groupItemTitle"),
                "tags": json.dumps(labels), "neg_risk": neg, "contract_type": ctype,
                "strike_lo": st.lo, "strike_hi": st.hi, "direction": direction, "label_fmt": st.fmt,
                "start_ts_utc": start, "end_ts_utc": end, "scheduled_end_ts_utc": sched_end,
                "settled_ts_utc": settled,
                "outcome": outcome_yes(m.get("outcomePrices"), m.get("outcomes")),
                "volume_shares": float(m.get("volumeNum") or 0.0),  # Gamma volumeNum counts shares, not dollars
                "yes_token_id": yes_tok, "no_token_id": no_tok,
            })
    mk = pd.DataFrame(rows)
    for c in ("start_ts_utc", "end_ts_utc", "scheduled_end_ts_utc", "settled_ts_utc"):
        mk[c] = pd.to_datetime(mk[c], utc=True)
    mk["start_et"] = mk["start_ts_utc"].dt.tz_convert(ET)
    mk["end_et"] = mk["end_ts_utc"].dt.tz_convert(ET)
    mk["outcome"] = mk["outcome"].astype("Int8")
    mk["usable_end_ts_utc"], mk["split_cutoff_ts_utc"] = mk["end_ts_utc"], pd.NaT  # apply_splits narrows these

    mk["excluded_reason"] = exclusion_reasons(mk, end_max)
    return mk


# ── step 10: ladder checks against the contract's own outcomes ────────────────
def _non_increasing(x: list[int]) -> bool:
    return all(a >= b for a, b in zip(x, x[1:]))


def check_ladders(mk: pd.DataFrame) -> pd.DataFrame:
    """Report-only (it reads outcomes): monotone outcomes in strike, or exactly one YES bucket,
    among kept rungs of one group that opened on the same day. Polymarket re-lists a barrier strike after it is touched, so
    rungs opened on different days answer different questions and are compared separately."""
    rows = []
    d = mk[mk["excluded_reason"].isna() & mk["contract_type"].isin(STRIKE_TYPES) & mk["outcome"].notna()]  # a void rung has no outcome to check
    for (eid, _), g in d.groupby(["event_id", d["start_et"].dt.date]):
        if len(g) < 2:
            continue
        if (g["direction"] == "bucket").any():
            ok = int(g["outcome"].sum()) == 1
            rows.append({"event_id": eid, "check": "one_yes_bucket", "passed": ok})
            continue
        ok = True
        for direction, h in g[g["direction"] != "bucket"].groupby("direction"):
            seq = [int(v) for v in h.sort_values("strike_lo")["outcome"]]
            ok &= _non_increasing(seq) if direction == "above" else _non_increasing(seq[::-1])
        rows.append({"event_id": eid, "check": "monotone", "passed": ok})
    return pd.DataFrame(rows, columns=["event_id", "check", "passed"])


def check_closes(mk: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    """Close ladders and buckets: the resolved outcome matches the stock's close on the end day.
    Report-only: it reads outcomes, so it excludes nothing.

    closes: company_id, date (ET trading day), close (as traded, not split-adjusted back).
    Rungs with no close in the five days up to the end day are reported as unchecked.
    """
    p = closes.assign(date=pd.to_datetime(closes["date"]).dt.date)
    px = dict(zip(zip(p["company_id"], p["date"]), p["close"]))
    rows = []
    d = mk[mk["excluded_reason"].isna() & mk["contract_type"].isin([CLOSE_LADDER, CLOSE_BUCKET])
           & mk["outcome"].notna() & mk["split_cutoff_ts_utc"].isna()]  # a split moves the close away from the opening strikes
    for r in d.itertuples():
        # a contract ending on a market holiday settles on the last close before it
        days = [r.end_et.date() - pd.Timedelta(days=k) for k in range(5)]
        c = next((px[(r.company_id, x)] for x in days if (r.company_id, x) in px), None)
        if c is None:
            rows.append({"event_id": r.event_id, "market_id": r.market_id, "check": "close", "passed": None})
            continue
        if r.direction == "bucket":
            pred = c >= r.strike_lo and (pd.isna(r.strike_hi) or c < r.strike_hi)
        elif r.direction == "below":
            pred = c < r.strike_lo
        else:
            pred = c > r.strike_lo
        rows.append({"event_id": r.event_id, "market_id": r.market_id, "check": "close",
                     "passed": bool(pred) == bool(r.outcome)})
    return pd.DataFrame(rows, columns=["event_id", "market_id", "check", "passed"])


# ── step 9: stock splits ──────────────────────────────────────────────────────
def apply_splits(mk: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """A price rung opened before a split quotes the old share price. It stays, but its usable
    life ends at the start of the split day (ET), because the split date was public at the time.

    splits: company_id, date (the split's first trading day, ET). `end_ts_utc` keeps the actual end.
    """
    mk = mk.copy()
    cut = {cid: sorted(pd.Timestamp(d).tz_localize(ET) for d in g["date"]) for cid, g in splits.groupby("company_id")}
    cutoffs = []
    for r in mk.itertuples():
        nxt = [t for t in cut.get(r.company_id, ()) if t > r.start_et] if r.contract_type in PRICE_STRIKE_TYPES else []
        cutoffs.append(nxt[0].tz_convert("UTC") if nxt and nxt[0] < r.end_ts_utc else pd.NaT)
    mk["split_cutoff_ts_utc"] = pd.to_datetime(pd.Series(cutoffs, index=mk.index), utc=True)
    mk["usable_end_ts_utc"] = mk["end_ts_utc"].where(mk["split_cutoff_ts_utc"].isna(), mk["split_cutoff_ts_utc"])
    mk["usable_end_et"] = mk["usable_end_ts_utc"].dt.tz_convert(ET)
    return mk


def build_events(mk: pd.DataFrame) -> pd.DataFrame:
    k = mk[mk["excluded_reason"].isna()]
    return (k.groupby("event_id")
            .agg(company_id=("company_id", "first"), contract_type=("contract_type", "first"),
                 title=("event_title", "first"), n_rungs=("market_id", "size"),
                 volume_shares=("volume_shares", "sum"), start_et=("start_et", "min"), end_et=("end_et", "max"))
            .reset_index())


# ── pull report ───────────────────────────────────────────────────────────────
def _md(df: pd.DataFrame) -> str:
    if df.empty:
        return "_none_\n"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines) + "\n"


def build_report(mk: pd.DataFrame, ev: pd.DataFrame, ladder: pd.DataFrame, close: pd.DataFrame) -> str:
    k = mk[mk["excluded_reason"].isna()]
    by_rungs = dict(groups=("event_id", "nunique"), rungs=("market_id", "size"),
                    no_volume=("volume_shares", lambda v: int((v <= 0).sum())))
    L = ["# Contract pull report", "",
         f"Rungs pulled: {len(mk)}. Kept: {len(k)} in {k['event_id'].nunique()} groups. "
         f"Kept rungs cut short by a stock split: {int(k['split_cutoff_ts_utc'].notna().sum())}.", "",
         "## Exclusions", "",
         _md(mk["excluded_reason"].fillna("(kept)").value_counts().rename_axis("reason").reset_index(name="rungs")),
         "## Kept rungs by type", "",
         _md(k.groupby("contract_type").agg(**by_rungs).reset_index()),
         "## Kept rungs by company", "",
         _md(k.groupby("company_id").agg(**by_rungs).sort_values("rungs", ascending=False).reset_index()),
         "## Ladder checks (report only, nothing is excluded)", "",
         _md(ladder.groupby("check")["passed"].agg(groups="size", passed="sum").reset_index()),
         "## Close checks (report only, rungs)", "",
         _md(close.assign(result=close["passed"].map({True: "passed", False: "failed"}).fillna("no close on end day"))
             .groupby("result").size().reset_index(name="rungs")),
         "## Groups failing a check (report only, all rungs stay)", ""]
    bad = pd.concat([ladder.loc[ladder["passed"] == False, ["event_id", "check"]],  # noqa: E712
                     close.loc[close["passed"] == False, ["event_id", "check"]]])  # noqa: E712
    failed = k[k["event_id"].isin(bad["event_id"])].merge(
        bad.groupby("event_id")["check"].agg(lambda c: ", ".join(sorted(set(c)))).rename("failed_checks"), on="event_id")
    L.append(_md(failed.groupby(["event_id", "company_id", "contract_type", "failed_checks"])
                 .agg(rungs=("market_id", "size"), title=("event_title", "first")).reset_index()))
    return "\n".join(L)
