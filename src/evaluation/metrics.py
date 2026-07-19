"""Evaluation metrics for W4-6 hypothesis tests (plan §4.1)."""
from __future__ import annotations

import numpy as np


def compute_r2_oos(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Out-of-sample R².  Can be negative. Never clipped.

    R²_OOS = 1 - SS_res / SS_tot
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0.0:
        return 0.0
    return float(1.0 - ss_res / ss_tot)


def compute_direction_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Fraction of samples where sign(ŷ) == sign(y).

    Excludes observations where y_true == 0.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    mask = y_true != 0.0
    if not np.any(mask):
        return float("nan")
    correct = np.sign(y_pred[mask]) == np.sign(y_true[mask])
    return float(np.mean(correct))


def compute_brier_near_resolution(
    y_pred_logit: np.ndarray,
    p_at_article: np.ndarray,
    resolution: np.ndarray,
    days_to_resolution: np.ndarray,
    max_days: float = 7.0,
) -> float:
    """Brier score restricted to observations near market resolution.

    Args:
        y_pred_logit: model output in log-odds space, shape (N,).
        p_at_article: market price at article time ∈ (0, 1), shape (N,).
        resolution: binary resolution outcome (0 or 1), shape (N,).
        days_to_resolution: days between article and market resolution, shape (N,).
        max_days: window threshold (default 7 days).

    Returns:
        Mean Brier score on the near-resolution subset, or nan if empty.
    """
    y_pred_logit = np.asarray(y_pred_logit, dtype=np.float64)
    p_at_article = np.asarray(p_at_article, dtype=np.float64)
    resolution = np.asarray(resolution, dtype=np.float64)
    days_to_resolution = np.asarray(days_to_resolution, dtype=np.float64)

    mask = days_to_resolution <= max_days
    if not np.any(mask):
        return float("nan")

    p_clipped = np.clip(p_at_article[mask], 1e-6, 1.0 - 1e-6)
    logit_p = np.log(p_clipped / (1.0 - p_clipped))
    p_hat = 1.0 / (1.0 + np.exp(-(logit_p + y_pred_logit[mask])))
    return float(np.mean((p_hat - resolution[mask]) ** 2))


def compute_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    p_at_article: np.ndarray | None = None,
    resolution: np.ndarray | None = None,
    days_to_resolution: np.ndarray | None = None,
) -> dict:
    """Compute all standard metrics in one call.

    Returns dict with keys: r2_oos, mse, direction_accuracy,
    brier_near_resolution.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    r2 = compute_r2_oos(y_true, y_pred)
    mse = float(np.mean((y_true - y_pred) ** 2))
    dir_acc = compute_direction_accuracy(y_true, y_pred)

    brier: float | None = None
    if (
        p_at_article is not None
        and resolution is not None
        and days_to_resolution is not None
    ):
        brier = compute_brier_near_resolution(
            y_pred_logit=y_pred,
            p_at_article=p_at_article,
            resolution=resolution,
            days_to_resolution=days_to_resolution,
        )

    return {
        "r2_oos": r2,
        "mse": mse,
        "direction_accuracy": dir_acc,
        "brier_near_resolution": brier,
    }
