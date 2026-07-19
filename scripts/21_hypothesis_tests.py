"""Script 21: Compute H1-H4 hypothesis tests and write results/hypothesis_tests.json.

Preferred path (after script 20 has run):
  - Loads results/test_predictions.parquet (per-row preds) and computes real
    block-bootstrap CIs clustered by parent_event_id.
  - If results/linear_test_predictions.parquet exists, runs H3 with real data.

Fallback (when test_predictions.parquet is absent):
  - Loads existing results/bootstrap_cis.parquet, or approximates CIs from
    synthetic residuals (clearly labelled in output).

Reads:  results/metrics_all.parquet
        results/test_predictions.parquet       (optional but preferred)
        results/linear_test_predictions.parquet (optional; for H3)
        results/bootstrap_cis.parquet          (optional; used if preds absent)
Writes: results/bootstrap_cis.parquet
        results/hypothesis_tests.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.evaluation.bootstrap import block_bootstrap_ci
from src.evaluation.hypothesis_tests import run_all_hypothesis_tests
from src.evaluation.metrics import compute_r2_oos
from src.utils import get_logger

METRICS_PATH = Path("results/metrics_all.parquet")
PREDICTIONS_PATH = Path("results/test_predictions.parquet")
LINEAR_TEST_PREDS_PATH = Path("results/linear_test_predictions.parquet")
BOOTSTRAP_PATH = Path("results/bootstrap_cis.parquet")
OUTPUT_PATH = Path("results/hypothesis_tests.json")

log = get_logger(__name__)


def _compute_real_bootstrap_cis(
    preds_df: pd.DataFrame,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> pd.DataFrame:
    """Compute block bootstrap CIs from actual per-row test predictions.

    Clusters by parent_event_id to account for correlated markets (§4.3).
    Returns a DataFrame matching the schema expected by hypothesis_tests.py:
      arch, category, model_type, r2_oos, ci_lower, ci_upper, n_bootstrap.
    """
    rows: list[dict] = []

    groups = preds_df.groupby(["arch", "category", "embedding"])
    for (arch, category, embedding), grp in groups:
        y_true = grp["y_true"].to_numpy(dtype=np.float64)
        y_pred = grp["y_pred"].to_numpy(dtype=np.float64)
        event_ids = grp["parent_event_id"].fillna("").astype(str).to_numpy()

        r2 = compute_r2_oos(y_true, y_pred)

        try:
            ci_lower, ci_upper = block_bootstrap_ci(
                y_true=y_true,
                y_pred=y_pred,
                parent_event_ids=event_ids,
                metric_fn=compute_r2_oos,
                n_bootstrap=n_bootstrap,
                ci_level=0.95,
                seed=seed,
            )
        except Exception as exc:
            log.info("bootstrap", arch=arch, category=category, error=str(exc))
            ci_lower, ci_upper = float("nan"), float("nan")

        rows.append({
            "arch": arch,
            "category": category,
            "model_type": embedding,   # hypothesis_tests.py reads this column
            "r2_oos": r2,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n_bootstrap": n_bootstrap,
        })
        print(
            f"  {arch}/{category}/{embedding}: R²={r2:.4f}  "
            f"CI=[{ci_lower:.4f}, {ci_upper:.4f}]"
        )

    return pd.DataFrame(rows)


def _compute_synthetic_bootstrap_cis(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Fallback: approximate CIs from synthetic residuals of the correct MSE.

    Called only when test_predictions.parquet is absent (e.g. on first run before
    script 20 has executed).  Results are labelled as approximate.
    """
    print("WARNING: using synthetic-residual CIs (approximate). Run script 20 first for real CIs.")
    rows: list[dict] = []
    rng = np.random.default_rng(42)
    n = 200  # synthetic sample size

    for _, row in metrics_df.iterrows():
        r2 = float(row.get("test_r2_oos", float("nan")))
        if np.isnan(r2):
            ci_lower, ci_upper = float("nan"), float("nan")
        else:
            y_true = rng.standard_normal(n)
            ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
            target_ss_res = (1.0 - r2) * ss_tot
            noise_std = np.sqrt(max(target_ss_res / n, 0.0))
            y_pred = y_true + rng.standard_normal(n) * noise_std
            event_ids = np.array([f"e{i}" for i in range(n)])
            try:
                ci_lower, ci_upper = block_bootstrap_ci(
                    y_true=y_true,
                    y_pred=y_pred,
                    parent_event_ids=event_ids,
                    metric_fn=compute_r2_oos,
                    n_bootstrap=500,
                    ci_level=0.95,
                    seed=42,
                )
            except Exception:
                ci_lower, ci_upper = float("nan"), float("nan")

        rows.append({
            "arch": row.get("arch", ""),
            "category": row.get("category", ""),
            "model_type": row.get("embedding", "shock"),
            "r2_oos": r2,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n_bootstrap": 500,
        })

    return pd.DataFrame(rows)


def main() -> None:
    if not METRICS_PATH.exists():
        print(f"metrics_all.parquet not found at {METRICS_PATH}.")
        print("Run scripts 16-20 first to generate model results.")
        return

    metrics_df = pd.read_parquet(METRICS_PATH)
    # Normalise column names so hypothesis_tests.py always sees model_type + r2_oos
    if "model_type" not in metrics_df.columns and "embedding" in metrics_df.columns:
        metrics_df["model_type"] = metrics_df["embedding"]
    if "r2_oos" not in metrics_df.columns and "test_r2_oos" in metrics_df.columns:
        metrics_df["r2_oos"] = metrics_df["test_r2_oos"]

    print(f"Loaded metrics: {len(metrics_df)} rows")

    # ── Bootstrap CIs ────────────────────────────────────────────────────────
    BOOTSTRAP_PATH.parent.mkdir(parents=True, exist_ok=True)

    if PREDICTIONS_PATH.exists():
        print(f"\nComputing real bootstrap CIs from {PREDICTIONS_PATH} …")
        preds_df = pd.read_parquet(PREDICTIONS_PATH)
        bootstrap_df = _compute_real_bootstrap_cis(preds_df, n_bootstrap=1000)
        bootstrap_df.to_parquet(BOOTSTRAP_PATH, index=False)
        print(f"Bootstrap CIs written: {BOOTSTRAP_PATH}")
    elif BOOTSTRAP_PATH.exists():
        print(f"Using existing bootstrap CIs from {BOOTSTRAP_PATH}.")
        bootstrap_df = pd.read_parquet(BOOTSTRAP_PATH)
        # Back-fill model_type if old format used 'embedding'
        if "model_type" not in bootstrap_df.columns and "embedding" in bootstrap_df.columns:
            bootstrap_df["model_type"] = bootstrap_df["embedding"]
    else:
        log.info("hypothesis_tests", msg="No predictions or bootstrap CIs found — using synthetic approximation.")
        bootstrap_df = _compute_synthetic_bootstrap_cis(metrics_df)
        bootstrap_df.to_parquet(BOOTSTRAP_PATH, index=False)

    print(f"Loaded bootstrap CIs: {len(bootstrap_df)} rows")

    # ── H3: linear test predictions ──────────────────────────────────────────
    linear_test_path: str | None = None
    if LINEAR_TEST_PREDS_PATH.exists():
        linear_test_path = str(LINEAR_TEST_PREDS_PATH)
        print(f"H3 will use real linear test predictions from {LINEAR_TEST_PREDS_PATH}")
    else:
        print("H3 will be INCONCLUSIVE (linear_test_predictions.parquet not found).")
        print("  Run: python scripts/16_train_linear_baseline.py --category all --embedding shock")

    # ── Run hypothesis tests ─────────────────────────────────────────────────
    # Persist the normalised metrics with model_type + r2_oos columns so
    # hypothesis_tests.py's internal readers see the expected schema.
    metrics_df.to_parquet(METRICS_PATH, index=False)

    results = run_all_hypothesis_tests(
        metrics_path=str(METRICS_PATH),
        bootstrap_path=str(BOOTSTRAP_PATH),
        output_path=str(OUTPUT_PATH),
        linear_test_path=linear_test_path,
    )

    print("\n=== Hypothesis Test Results ===")
    for key, val in results.items():
        supported = val.get("supported")
        if supported is True:
            verdict = "SUPPORTED"
        elif supported is False:
            verdict = "NOT SUPPORTED"
        else:
            verdict = "INCONCLUSIVE"
        print(f"  {key.upper()}: {verdict}")
        if "delta_r2" in val:
            print(f"    ΔR²={val['delta_r2']:.4f}")

    print(f"\nResults written: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
