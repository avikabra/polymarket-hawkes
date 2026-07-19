"""Tests for src/evaluation/metrics.py."""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.evaluation.metrics import compute_r2_oos, compute_direction_accuracy


def test_r2_oos_perfect():
    y = np.array([1.0, 2.0, 3.0])
    assert compute_r2_oos(y, y) == pytest.approx(1.0)


def test_r2_oos_mean_predictor():
    y = np.array([1.0, 2.0, 3.0])
    y_pred = np.full_like(y, y.mean())
    assert compute_r2_oos(y, y_pred) == pytest.approx(0.0, abs=1e-10)


def test_r2_oos_negative():
    y = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([3.0, 2.0, 1.0])  # reversed — worse than mean predictor
    assert compute_r2_oos(y, y_pred) < 0.0


def test_r2_oos_constant_y():
    """When all y_true are equal, SS_tot=0; function should return 0 not nan/inf."""
    y = np.array([2.0, 2.0, 2.0])
    y_pred = np.array([1.0, 2.0, 3.0])
    result = compute_r2_oos(y, y_pred)
    assert result == 0.0


def test_r2_oos_half_explained():
    """Construct a prediction where R² should be exactly 0.5."""
    rng = np.random.default_rng(7)
    y = rng.standard_normal(100)
    ss_tot = np.sum((y - y.mean()) ** 2)
    # SS_res = 0.5 * SS_tot → R² = 0.5
    noise = rng.standard_normal(100)
    noise = noise * np.sqrt(0.5 * ss_tot / np.sum(noise ** 2))
    y_pred = y - noise
    result = compute_r2_oos(y, y_pred)
    assert result == pytest.approx(0.5, abs=1e-10)


def test_direction_accuracy_perfect():
    y = np.array([1.0, -1.0, 2.0])
    assert compute_direction_accuracy(y, y) == pytest.approx(1.0)


def test_direction_accuracy_excludes_zero():
    y_true = np.array([0.0, 1.0, -1.0])
    y_pred = np.array([1.0, 1.0, -1.0])  # first entry excluded (y_true=0)
    assert compute_direction_accuracy(y_true, y_pred) == pytest.approx(1.0)


def test_direction_accuracy_all_wrong():
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([-1.0, -2.0, -3.0])
    assert compute_direction_accuracy(y_true, y_pred) == pytest.approx(0.0)


def test_direction_accuracy_all_zero_true():
    """When all y_true == 0, result should be nan (no valid observations)."""
    y_true = np.array([0.0, 0.0, 0.0])
    y_pred = np.array([1.0, -1.0, 0.5])
    result = compute_direction_accuracy(y_true, y_pred)
    assert math.isnan(result)


def test_direction_accuracy_half():
    y_true = np.array([1.0, 1.0, -1.0, -1.0])
    y_pred = np.array([1.0, -1.0, -1.0, 1.0])  # 2 correct, 2 wrong
    assert compute_direction_accuracy(y_true, y_pred) == pytest.approx(0.5)
