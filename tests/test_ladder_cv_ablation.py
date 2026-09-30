"""Tests for src/analysis/ladder_cv_ablation.py's fold-stratification helper.

The bug it exists to prevent: the original temporal-split ladder ablation put
every singleton-cohort row in val and every huge-cohort row in test, making
the comparison uninformative. These tests check that stratified_cohort_folds
spreads cohort sizes roughly evenly across folds instead.
"""

import numpy as np
import pandas as pd

from src.analysis.ladder_cv_ablation import stratified_cohort_folds


def test_each_fold_gets_a_mix_of_cohort_sizes():
    # 100 singleton rows + 100 huge-cohort rows — the adversarial case that
    # broke the temporal split (all singletons in one bucket, all huge in another).
    sizes = pd.Series([1] * 100 + [400] * 100)
    folds = stratified_cohort_folds(sizes, n_splits=5, seed=0)

    assert len(folds) == 200
    assert set(folds) == {0, 1, 2, 3, 4}

    for fold_idx in range(5):
        in_fold = sizes[folds == fold_idx]
        n_singleton = (in_fold == 1).sum()
        n_huge = (in_fold == 400).sum()
        # Each fold should have both, not be entirely one or the other.
        assert n_singleton > 0, f"fold {fold_idx} has no singleton-cohort rows"
        assert n_huge > 0, f"fold {fold_idx} has no huge-cohort rows"


def test_folds_are_roughly_balanced_in_size():
    sizes = pd.Series(np.concatenate([np.full(60, 1), np.full(60, 50), np.full(60, 300)]))
    folds = stratified_cohort_folds(sizes, n_splits=5, seed=1)
    counts = pd.Series(folds).value_counts()
    assert counts.min() >= 30  # 180/5 = 36 expected; allow slack, not exact equality
    assert counts.max() <= 42


def test_handles_too_few_rows_for_requested_splits_gracefully():
    # 6 rows, 5 splits — StratifiedKFold with 4 strata would fail (each
    # stratum would have <5 members); must fall back without raising.
    sizes = pd.Series([1, 2, 3, 4, 5, 6])
    folds = stratified_cohort_folds(sizes, n_splits=5, seed=0)
    assert len(folds) == 6
    assert set(folds) <= {0, 1, 2, 3, 4}


def test_all_identical_cohort_sizes_does_not_crash():
    sizes = pd.Series([10] * 50)
    folds = stratified_cohort_folds(sizes, n_splits=5, seed=0)
    assert len(folds) == 50
    assert set(folds) == {0, 1, 2, 3, 4}


def test_deterministic_given_seed():
    sizes = pd.Series([1, 5, 20, 100, 1, 5, 20, 100] * 10)
    folds_a = stratified_cohort_folds(sizes, n_splits=4, seed=7)
    folds_b = stratified_cohort_folds(sizes, n_splits=4, seed=7)
    assert np.array_equal(folds_a, folds_b)
