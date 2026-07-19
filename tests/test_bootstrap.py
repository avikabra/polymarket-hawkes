"""Tests for block_bootstrap_ci in src/evaluation/bootstrap.py."""
from __future__ import annotations

import numpy as np
import pytest

from src.evaluation.bootstrap import block_bootstrap_ci
from src.evaluation.metrics import compute_r2_oos


def test_ci_wider_under_heavy_clustering():
    """CI should be wider when obs share few large clusters vs. many small clusters.

    We use 10 clusters of size 10 (high within-cluster correlation) vs.
    100 singleton clusters (standard i.i.d. bootstrap).  The within-cluster
    correlation is induced by adding a shared cluster-level random effect to
    both y_true and y_pred so the R² values vary a lot across cluster draws.
    """
    rng = np.random.default_rng(42)
    n_clusters = 10
    cluster_size = 10
    n = n_clusters * cluster_size

    # Build a dataset with strong cluster-level variation
    cluster_effects = rng.standard_normal(n_clusters) * 3.0  # large cluster effects
    y_true = np.zeros(n)
    y_pred = np.zeros(n)
    few_cluster_ids = np.empty(n, dtype=object)
    for c in range(n_clusters):
        idx = slice(c * cluster_size, (c + 1) * cluster_size)
        y_true[idx] = cluster_effects[c] + rng.standard_normal(cluster_size) * 0.1
        y_pred[idx] = cluster_effects[c] + rng.standard_normal(cluster_size) * 0.1
        few_cluster_ids[idx] = f"event_{c}"

    # Many singletons → standard bootstrap
    many_cluster_ids = np.array([f"obs_{i}" for i in range(n)])

    ci_few = block_bootstrap_ci(
        y_true, y_pred, few_cluster_ids, compute_r2_oos, n_bootstrap=500, seed=0
    )
    ci_many = block_bootstrap_ci(
        y_true, y_pred, many_cluster_ids, compute_r2_oos, n_bootstrap=500, seed=0
    )

    width_few = ci_few[1] - ci_few[0]
    width_many = ci_many[1] - ci_many[0]
    assert width_few > width_many, (
        f"Few-cluster CI width {width_few:.4f} should exceed "
        f"many-cluster CI width {width_many:.4f}"
    )


def test_ci_contains_point_estimate():
    """CI should usually contain the point estimate (probabilistic — high n_bootstrap)."""
    rng = np.random.default_rng(2)
    y_true = rng.standard_normal(80)
    y_pred = rng.standard_normal(80)
    ids = np.array([f"e{i // 4}" for i in range(80)])

    ci = block_bootstrap_ci(y_true, y_pred, ids, compute_r2_oos, n_bootstrap=500, seed=1)
    point = compute_r2_oos(y_true, y_pred)
    assert ci[0] <= point <= ci[1], (
        f"Point estimate {point:.4f} not in CI [{ci[0]:.4f}, {ci[1]:.4f}]"
    )


def test_ci_returns_two_floats():
    """Return value is a (float, float) tuple."""
    rng = np.random.default_rng(3)
    y_true = rng.standard_normal(30)
    y_pred = rng.standard_normal(30)
    ids = np.array([f"e{i}" for i in range(30)])
    ci = block_bootstrap_ci(y_true, y_pred, ids, compute_r2_oos, n_bootstrap=50, seed=0)
    assert isinstance(ci, tuple) and len(ci) == 2
    lower, upper = ci
    assert isinstance(lower, float) and isinstance(upper, float)
    assert lower <= upper


def test_ci_lower_less_than_upper():
    """Lower bound must be <= upper bound for any sane input."""
    rng = np.random.default_rng(99)
    y_true = rng.standard_normal(50)
    y_pred = y_true + rng.standard_normal(50) * 0.1
    ids = np.array([f"ev{i % 5}" for i in range(50)])
    ci = block_bootstrap_ci(y_true, y_pred, ids, compute_r2_oos, n_bootstrap=100, seed=5)
    assert ci[0] <= ci[1]


def test_ci_seed_reproducibility():
    """Same seed must give same CI."""
    rng = np.random.default_rng(7)
    y_true = rng.standard_normal(40)
    y_pred = rng.standard_normal(40)
    ids = np.array([f"e{i % 8}" for i in range(40)])

    ci_a = block_bootstrap_ci(y_true, y_pred, ids, compute_r2_oos, n_bootstrap=100, seed=42)
    ci_b = block_bootstrap_ci(y_true, y_pred, ids, compute_r2_oos, n_bootstrap=100, seed=42)
    assert ci_a == ci_b
