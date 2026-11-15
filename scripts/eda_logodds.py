"""EDA script: log-odds distribution and event-time visuals for 1-min bar data.

Produces five figures and a written read-file. Designed to run on any set of
bars_1min parquet files (sports legacy or company). Parameterised via CLI.

Usage:
    uv run python scripts/eda_logodds.py --label smoketest_sports

All prices read from the `close_lo` column, which the resampler writes in
log-odds units (confirmed: range observed ~[-6.2, +2.2], not [0,1]). We
never apply logit() here — the column is already log-odds.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")  # headless — no display required
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils import get_logger

log = get_logger(__name__)

# Fraction of a minute-window counted as "zero move" if |Δ| < EPS
EPS = 0.01  # ~1 log-odds centile; stated explicitly in figures


# ─────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_bars(bars_root: Path) -> pd.DataFrame:
    """Load all bar parquet files under bars_root into a single DataFrame.

    Adds a `contract_id` column derived from the filename stem (the market_id
    hash). Raises if no files are found.
    """
    files = sorted(bars_root.rglob("part-*.parquet"))
    if not files:
        raise RuntimeError(
            f"No parquet files found under {bars_root}. "
            "Run script 03 first to generate bars."
        )
    log.info("loading bars", extra={"n_files": len(files), "root": str(bars_root)})
    parts = []
    for f in files:
        df = pd.read_parquet(f)
        # Extract market_id from filename: "part-<market_id>.parquet"
        df["contract_id"] = f.stem.removeprefix("part-")
        parts.append(df)
    bars = pd.concat(parts, ignore_index=True)
    log.info("bars loaded", extra={"rows": len(bars), "contracts": bars["contract_id"].nunique()})
    return bars


def _load_universe(universe_path: Path) -> pd.DataFrame | None:
    """Return universe DataFrame, or None if path does not exist."""
    if not universe_path.exists():
        log.warning("universe file not found — proceeding without it", extra={"path": str(universe_path)})
        return None
    return pd.read_parquet(universe_path)


def _load_events(events_path: Path | None) -> pd.DataFrame | None:
    """Load optional events parquet (must have market_id or group_id + event_ts)."""
    if events_path is None:
        return None
    if not events_path.exists():
        raise RuntimeError(f"--events path does not exist: {events_path}")
    df = pd.read_parquet(events_path)
    # Normalise to a common key name
    if "group_id" in df.columns and "market_id" not in df.columns:
        df = df.rename(columns={"group_id": "market_id"})
    required = {"market_id", "event_ts"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"events parquet missing columns: {missing}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Delta computation (core — log-odds space, no logit applied)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_deltas(bars: pd.DataFrame, delta_hours: int) -> pd.DataFrame:
    """Return per-row y_logit_Δ = close_lo[t+Δ] − close_lo[t].

    `close_lo` is already in log-odds (written by resampler.py), so we
    compute the difference directly without any logit transformation.
    Aligns t+Δ on the minute grid by shifting by delta_mins steps.
    """
    delta_mins = delta_hours * 60
    result_parts = []
    for cid, grp in bars.groupby("contract_id"):
        grp = grp.sort_values("ts_min").reset_index(drop=True)
        # forward shift by delta_mins bars (each bar = 1 minute)
        grp["close_lo_future"] = grp["close_lo"].shift(-delta_mins)
        grp["y_logit_delta"] = grp["close_lo_future"] - grp["close_lo"]
        # drop rows where future doesn't exist
        grp = grp.dropna(subset=["y_logit_delta"])
        grp["contract_id"] = cid
        result_parts.append(grp)
    if not result_parts:
        raise RuntimeError("No delta rows computed — bars may be too short for the chosen delta_hours.")
    return pd.concat(result_parts, ignore_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: 6-hour log-odds change distribution
# ─────────────────────────────────────────────────────────────────────────────

def fig1_delta_distribution(
    deltas: pd.DataFrame, delta_hours: int, out_dir: Path, label: str
) -> None:
    vals = deltas["y_logit_delta"].dropna().values
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(vals, bins=120, color="steelblue", edgecolor="none", alpha=0.8)
    ax.axvline(0, color="crimson", lw=1.2, ls="--", label="zero")
    ax.set_xlabel(f"y_logit_Δ  (log-odds change over {delta_hours}h)", fontsize=11)
    ax.set_ylabel("Count (bar-observations)", fontsize=11)
    ax.set_title(
        f"[{label}] Distribution of {delta_hours}h log-odds price changes\n"
        f"n={len(vals):,}  mean={vals.mean():.4f}  std={vals.std():.4f}",
        fontsize=11,
    )
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = out_dir / f"fig1_delta_distribution_{label}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("saved fig1", extra={"path": str(out)})


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: Zero-move share per contract
# ─────────────────────────────────────────────────────────────────────────────

def fig2_zero_move_share(
    deltas: pd.DataFrame, out_dir: Path, label: str
) -> None:
    per_contract = (
        deltas.groupby("contract_id")["y_logit_delta"]
        .agg(
            total="count",
            zero_count=lambda s: (s.abs() < EPS).sum(),
        )
        .assign(zero_share=lambda d: d["zero_count"] / d["total"])
        .sort_values("zero_share", ascending=False)
        .reset_index()
    )
    overall = (deltas["y_logit_delta"].abs() < EPS).mean()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Left: histogram of per-contract zero share
    ax = axes[0]
    ax.hist(per_contract["zero_share"], bins=30, color="darkorange", edgecolor="none", alpha=0.85)
    ax.axvline(overall, color="crimson", lw=1.4, ls="--", label=f"overall={overall:.3f}")
    ax.set_xlabel("Fraction of windows with |y_logit_Δ| < EPS", fontsize=10)
    ax.set_ylabel("# contracts", fontsize=10)
    ax.set_title(f"[{label}] Zero-move share per contract\n(EPS={EPS})", fontsize=10)
    ax.legend(fontsize=9)

    # Right: ranked bar of per-contract zero share (top-30 if many)
    ax2 = axes[1]
    top = per_contract.head(min(30, len(per_contract)))
    x = np.arange(len(top))
    ax2.bar(x, top["zero_share"], color="darkorange", alpha=0.8)
    ax2.axhline(overall, color="crimson", lw=1.2, ls="--", label=f"overall={overall:.3f}")
    ax2.set_xticks([])
    ax2.set_xlabel("Contracts (ranked by zero-share, highest first)", fontsize=10)
    ax2.set_ylabel("Zero-move fraction", fontsize=10)
    ax2.set_title(f"Ranked zero-move share (top {len(top)} of {len(per_contract)})", fontsize=10)
    ax2.legend(fontsize=9)

    fig.tight_layout()
    out = out_dir / f"fig2_zero_move_share_{label}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("saved fig2", extra={"path": str(out), "overall_zero_share": round(float(overall), 4)})


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3: Trade frequency & volume by contract
# ─────────────────────────────────────────────────────────────────────────────

def fig3_trade_frequency_volume(
    bars: pd.DataFrame, out_dir: Path, label: str
) -> None:
    per_contract = (
        bars.groupby("contract_id")
        .agg(
            active_bars=("trade_count", lambda s: (s > 0).sum()),
            total_volume=("volume_usdc", "sum"),
        )
        .reset_index()
        .sort_values("total_volume", ascending=False)
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Scatter: active bars vs total volume
    ax = axes[0]
    ax.scatter(per_contract["active_bars"], per_contract["total_volume"],
               alpha=0.6, s=20, color="teal")
    ax.set_xlabel("Active bars (minutes with ≥1 trade)", fontsize=10)
    ax.set_ylabel("Total volume (USDC)", fontsize=10)
    ax.set_title(f"[{label}] Active bars vs volume per contract\nn={len(per_contract)}", fontsize=10)
    ax.set_yscale("log" if per_contract["total_volume"].max() / max(per_contract["total_volume"].min(), 1) > 100 else "linear")

    # Ranked bar: total volume
    ax2 = axes[1]
    top_n = min(40, len(per_contract))
    top = per_contract.head(top_n)
    ax2.bar(np.arange(top_n), top["total_volume"], color="teal", alpha=0.8)
    ax2.set_xticks([])
    ax2.set_xlabel(f"Contracts (top {top_n} by volume)", fontsize=10)
    ax2.set_ylabel("Total volume (USDC)", fontsize=10)
    ax2.set_title("Ranked total volume", fontsize=10)

    fig.tight_layout()
    out = out_dir / f"fig3_trade_frequency_volume_{label}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("saved fig3", extra={"path": str(out), "n_contracts": len(per_contract)})


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4: Demean + normalize representative contracts
# ─────────────────────────────────────────────────────────────────────────────

def fig4_demean_normalize(
    bars: pd.DataFrame, out_dir: Path, label: str, n_contracts: int = 4
) -> None:
    """Pick the n_contracts with the most active bars for illustration."""
    activity = (
        bars.groupby("contract_id")["trade_count"]
        .apply(lambda s: (s > 0).sum())
        .sort_values(ascending=False)
    )
    chosen = activity.head(n_contracts).index.tolist()

    fig, axes = plt.subplots(n_contracts, 2, figsize=(14, 3 * n_contracts))
    if n_contracts == 1:
        axes = axes[None, :]  # ensure 2D indexing

    for row_i, cid in enumerate(chosen):
        grp = bars[bars["contract_id"] == cid].sort_values("ts_min")
        # close_lo is already log-odds — treat directly
        raw = grp["close_lo"].values
        ts = grp["ts_min"].values

        std = raw.std()
        norm = (raw - raw.mean()) / std if std > 0 else raw - raw.mean()

        short_id = cid[:10]

        ax_raw = axes[row_i, 0]
        ax_raw.plot(ts, raw, lw=0.5, color="navy", alpha=0.8)
        ax_raw.set_title(f"Raw log-odds  [{short_id}…]", fontsize=9)
        ax_raw.set_ylabel("log-odds", fontsize=8)
        ax_raw.set_xlabel("ts_min (unix s)", fontsize=8)

        ax_norm = axes[row_i, 1]
        ax_norm.plot(ts, norm, lw=0.5, color="darkgreen", alpha=0.8)
        ax_norm.axhline(0, color="grey", lw=0.8, ls="--")
        ax_norm.set_title(f"Demeaned+unit-var  [{short_id}…]", fontsize=9)
        ax_norm.set_ylabel("normalised", fontsize=8)
        ax_norm.set_xlabel("ts_min (unix s)", fontsize=8)

    fig.suptitle(
        f"[{label}] Raw vs demeaned/normalised log-odds  (top {n_contracts} by activity)",
        fontsize=11,
    )
    fig.tight_layout()
    out = out_dir / f"fig4_demean_normalize_{label}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("saved fig4", extra={"path": str(out), "contracts": chosen})


# ─────────────────────────────────────────────────────────────────────────────
# Figure 5: Event-time plot
# ─────────────────────────────────────────────────────────────────────────────

def fig5_event_time(
    bars: pd.DataFrame,
    events: pd.DataFrame | None,
    out_dir: Path,
    label: str,
    window_pre_mins: int = 120,
    window_post_mins: int = 360,
) -> None:
    """Align log-odds in event time; overlay average across events.

    If `events` is None, generate synthetic events from bar midpoints
    and label clearly as machinery-only.
    """
    is_synthetic = events is None
    if is_synthetic:
        # Build synthetic events: one per contract at the midpoint of its series
        rng = np.random.default_rng(42)
        synthetic_rows = []
        for cid, grp in bars.groupby("contract_id"):
            ts_vals = grp["ts_min"].values
            if len(ts_vals) < window_pre_mins + window_post_mins:
                continue
            # Pick a random ts in the "safe" interior
            lo = int(window_pre_mins * 60)
            hi = int(len(ts_vals) - window_post_mins) * 60
            if hi <= lo:
                continue
            mid_ts = int(ts_vals[len(ts_vals) // 2])
            synthetic_rows.append({"market_id": cid, "event_ts": mid_ts})
        if not synthetic_rows:
            log.warning("not enough bars to build synthetic events — skipping fig5")
            return
        events = pd.DataFrame(synthetic_rows)
        log.info("synthetic events created", extra={"n": len(events)})

    # Pre-group bars by contract_id for O(1) per-event lookup
    bars_by_cid: dict[str, pd.DataFrame] = {
        cid: grp.sort_values("ts_min")
        for cid, grp in bars.groupby("contract_id")
    }

    # Build event-time traces
    traces = []
    for _, ev_row in events.iterrows():
        mid = ev_row["market_id"]
        evt = int(ev_row["event_ts"])  # unix seconds

        grp = bars_by_cid.get(mid)
        if grp is None or grp.empty:
            continue
        ts = grp["ts_min"].values
        lo = grp["close_lo"].values

        # Relative time in minutes
        rel_min = (ts - evt) / 60.0

        # Select window
        mask = (rel_min >= -window_pre_mins) & (rel_min <= window_post_mins)
        if mask.sum() < 10:
            continue

        rel = rel_min[mask]
        vals = lo[mask]
        # Anchor: subtract value at t=0 (nearest bar)
        idx0 = np.argmin(np.abs(rel))
        anchor = vals[idx0]
        traces.append(pd.Series(vals - anchor, index=rel))

    if not traces:
        log.warning("no valid event traces — skipping fig5")
        return

    # Interpolate onto a common grid
    grid = np.arange(-window_pre_mins, window_post_mins + 1, dtype=float)
    aligned = np.full((len(traces), len(grid)), np.nan)
    for i, trace in enumerate(traces):
        # Only fill grid points that have data
        interp_vals = np.interp(grid, trace.index, trace.values,
                                left=np.nan, right=np.nan)
        aligned[i] = interp_vals

    mean_trace = np.nanmean(aligned, axis=0)
    # 25th/75th percentile band
    lo_band = np.nanpercentile(aligned, 25, axis=0)
    hi_band = np.nanpercentile(aligned, 75, axis=0)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(grid, lo_band, hi_band, alpha=0.25, color="steelblue", label="IQR")
    ax.plot(grid, mean_trace, color="steelblue", lw=1.5, label="Mean log-odds Δ")
    ax.axvline(0, color="crimson", lw=1.2, ls="--", label="Event t=0")
    ax.axhline(0, color="grey", lw=0.8, ls=":")
    ax.set_xlabel("Minutes relative to event", fontsize=11)
    ax.set_ylabel("Log-odds change from t=0", fontsize=11)

    synth_tag = "  [SYNTHETIC — machinery validation only, not real matches]" if is_synthetic else ""
    ax.set_title(
        f"[{label}] Event-time log-odds  "
        f"(n={len(traces)} events,  −{window_pre_mins}..+{window_post_mins} min){synth_tag}",
        fontsize=10,
    )
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = out_dir / f"fig5_event_time_{label}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    log.info("saved fig5", extra={"path": str(out), "n_events": len(traces), "synthetic": is_synthetic})


# ─────────────────────────────────────────────────────────────────────────────
# Written read
# ─────────────────────────────────────────────────────────────────────────────

def write_read(
    out_path: Path,
    label: str,
    delta_hours: int,
    n_contracts: int,
    n_bars: int,
    events_synthetic: bool,
) -> None:
    synthetic_note = (
        "Because no `--events` file was supplied, Figure 5 uses **synthetic** event "
        "timestamps (one per contract, at its series midpoint, RNG seed=42). "
        "This validates the event-time alignment machinery only; no causal signal "
        "should be read from the shape."
    ) if events_synthetic else (
        "Figure 5 uses real event timestamps from the supplied `--events` file."
    )

    text = f"""# Log-Odds EDA: {label}

> **Note:** These figures are **machinery-validation outputs on legacy sports/politics bars**
> (label: `{label}`). The bar pool contains {n_bars:,} 1-minute bars from {n_contracts}
> contracts. Real company-bar analysis will follow once company bars exist.

---

## Figure 1 — {delta_hours}h Log-Odds Change Distribution

Histogram of `y_logit_Δ = close_lo[t+Δ] − close_lo[t]` pooled across all contracts
(Δ = {delta_hours} hours, aligned on the minute grid).
`close_lo` is already in log-odds; no logit transform is applied here.
A sharp spike at zero indicates periods of market inactivity (no trades, LOCF fill).
A fat-tailed distribution with both positive and negative mass is healthy: it means
the model has something to predict. If this histogram is almost entirely zero,
target selection is degenerate and Δ should be shortened or contracts filtered.

## Figure 2 — Zero-Move Share (EPS = {EPS})

Per-contract and overall fraction of Δ-windows where |y_logit_Δ| < {EPS}.
This directly addresses Prof. Kelly's concern that inactivity manufactures zeros.
A contract with >90% zero-move share contributes almost no signal and should be
excluded from the training universe. The overall zero-share is the headline number:
values above ~70% suggest the reaction window is dominated by LOCF-filled bars and
the market was thinly traded in this period.

## Figure 3 — Trade Frequency & Volume by Contract

Scatter of active bars (minutes with ≥1 trade) versus total USDC volume, plus a
ranked bar chart. This surfaces volume concentration: if a handful of contracts
account for almost all activity, the training set is effectively driven by a few
markets. Contracts with near-zero active bars should be filtered before training.

## Figure 4 — Demean + Normalize

Raw log-odds series vs demeaned-and-unit-variance-normalized series for the top
{n_contracts} most-active contracts. Confirms that the normalization removes
level differences across contracts (different strike prices, different market
regimes) and expresses everything as standard-deviation moves. This is the form
the model should consume.

## Figure 5 — Event-Time Plot

Log-odds aligned in event time (x = minutes relative to event, y = log-odds
change from t=0). {synthetic_note}
For real event data, a visible step or drift after t=0 would indicate a news shock.
Flat mean ± wide IQR indicates either no average effect (expected for a diverse
event pool) or insufficient data to detect one.

---

*Generated by `scripts/eda_logodds.py --label {label}`.*
*Company-bar read pending script 03 rerun on company trade data.*
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    log.info("written read", extra={"path": str(out_path)})


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Log-odds EDA: 5 figures + written read")
    p.add_argument("--bars-root", default="data/polymarket/bars_1min",
                   help="Root of 1-min bar parquet tree (default: data/polymarket/bars_1min)")
    p.add_argument("--universe", default="data/polymarket/universe.parquet",
                   help="Universe parquet (default: data/polymarket/universe.parquet)")
    p.add_argument("--out-dir", default="reports/figures",
                   help="Output directory for PNGs (default: reports/figures)")
    p.add_argument("--events", default=None,
                   help="Optional parquet with (market_id, event_ts) rows for fig5")
    p.add_argument("--delta-hours", type=int, default=6,
                   help="Reaction window length in hours (default: 6)")
    p.add_argument("--label", default="run",
                   help="Tag stamped into filenames and titles (e.g. smoketest_sports)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    bars_root = Path(args.bars_root)
    universe_path = Path(args.universe)
    out_dir = Path(args.out_dir)
    events_path = Path(args.events) if args.events else None

    out_dir.mkdir(parents=True, exist_ok=True)

    # Load data — fail loud on missing bars
    bars = _load_bars(bars_root)
    _load_universe(universe_path)  # informational only; not required for figures
    events = _load_events(events_path)
    events_synthetic = events is None

    n_bars = len(bars)
    n_contracts = bars["contract_id"].nunique()
    log.info("dataset summary", extra={"bars": n_bars, "contracts": n_contracts})

    # Compute deltas once, reuse across figures 1 and 2
    log.info("computing deltas", extra={"delta_hours": args.delta_hours})
    deltas = _compute_deltas(bars, args.delta_hours)

    # Generate all five figures
    fig1_delta_distribution(deltas, args.delta_hours, out_dir, args.label)
    fig2_zero_move_share(deltas, out_dir, args.label)
    fig3_trade_frequency_volume(bars, out_dir, args.label)
    fig4_demean_normalize(bars, out_dir, args.label)
    fig5_event_time(bars, events, out_dir, args.label)

    # Written read
    read_path = Path("reports/logodds_eda_read.md")
    write_read(
        read_path,
        label=args.label,
        delta_hours=args.delta_hours,
        n_contracts=n_contracts,
        n_bars=n_bars,
        events_synthetic=events_synthetic,
    )

    print(f"\nDone. Figures written to {out_dir}/")
    print(f"Written read: {read_path}")


if __name__ == "__main__":
    main()
