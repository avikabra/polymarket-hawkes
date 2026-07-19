"""Block bootstrap confidence intervals clustered by parent_event_id."""
from __future__ import annotations

import numpy as np

try:
    from joblib import Parallel, delayed
    _JOBLIB_AVAILABLE = True
except ImportError:
    _JOBLIB_AVAILABLE = False


def _one_bootstrap(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    unique_ids: np.ndarray,
    id_to_mask: dict,
    metric_fn: callable,
    rng_seed: int,
) -> float:
    """Draw one bootstrap sample and return metric value."""
    rng = np.random.default_rng(rng_seed)
    sampled_ids = rng.choice(unique_ids, size=len(unique_ids), replace=True)
    indices = np.concatenate([id_to_mask[uid] for uid in sampled_ids])
    return metric_fn(y_true[indices], y_pred[indices])


def block_bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    parent_event_ids: np.ndarray,
    metric_fn: callable,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    seed: int = 42,
    n_jobs: int = 1,
) -> tuple[float, float]:
    """Block bootstrap confidence interval for metric_fn(y_true, y_pred).

    Resamples entire parent_event_id clusters with replacement.

    Args:
        y_true: ground-truth array, shape (N,).
        y_pred: predicted array, shape (N,).
        parent_event_ids: cluster labels, shape (N,).
        metric_fn: callable(y_true, y_pred) -> float.
        n_bootstrap: number of bootstrap iterations.
        ci_level: confidence level (e.g. 0.95 for 95% CI).
        seed: base random seed.
        n_jobs: number of parallel workers (requires joblib).

    Returns:
        (lower, upper) CI bounds as floats.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    parent_event_ids = np.asarray(parent_event_ids)

    unique_ids = np.unique(parent_event_ids)

    # Build index map: event_id -> array of row indices
    id_to_mask: dict = {}
    for uid in unique_ids:
        id_to_mask[uid] = np.where(parent_event_ids == uid)[0]

    seeds = np.random.default_rng(seed).integers(0, 2**31, size=n_bootstrap)

    if n_jobs > 1 and _JOBLIB_AVAILABLE:
        boot_stats = Parallel(n_jobs=n_jobs)(
            delayed(_one_bootstrap)(
                y_true, y_pred, unique_ids, id_to_mask, metric_fn, int(s)
            )
            for s in seeds
        )
    else:
        boot_stats = [
            _one_bootstrap(y_true, y_pred, unique_ids, id_to_mask, metric_fn, int(s))
            for s in seeds
        ]

    boot_stats = np.array(boot_stats, dtype=np.float64)
    alpha = 1.0 - ci_level
    lower = float(np.nanpercentile(boot_stats, 100 * alpha / 2))
    upper = float(np.nanpercentile(boot_stats, 100 * (1.0 - alpha / 2)))
    return lower, upper
