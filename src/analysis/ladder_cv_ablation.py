"""Cohort-stratified k-fold CV comparison for Thread 2's ladder correction.

Kept separate from scripts/16b_ladder_cv_ablation.py (which does the parquet
I/O and model fitting) so the fold-assignment logic can be unit-tested against
synthetic cohort sizes without real embeddings or shock_embeddings.parquet.

Why non-temporal CV, not the production train/val/test split: the original
head-to-head ablation (scripts/16_train_linear_baseline.py --target
y_logit_24h vs y_logit_24h_ladder) used the real temporal split and produced
a meaningless comparison — val (n=20) was entirely singleton cohorts
(ladder_n_members_used_24h=1 for every row, so y_logit_24h_ladder was
byte-identical to y_logit_24h there), while test's cohorts averaged 347
members. That's not a fair test of whether isotonic pooling helps; it's an
artifact of large ladders (Apple/Microsoft-scale, 50+ strikes) clustering in
particular time windows under this corpus's real date distribution. This
script asks a different, narrower question than the production split is for:
does isotonic-pooling improve a linear model's fit to the reaction signal,
not whether the pipeline can forecast the future. scripts/09b_matching_ablation.py
already uses this same all-pairs-no-split precedent for the same reason
(evaluating a scoring function's correlation with outcomes, not forecasting).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold


def stratified_cohort_folds(
    cohort_sizes: pd.Series, n_splits: int = 5, seed: int = 42
) -> np.ndarray:
    """Assign each row a fold index in [0, n_splits) so every fold gets a
    representative mix of cohort sizes, instead of e.g. all-singleton in one
    fold and all-huge in another — the exact failure mode that made the
    original temporal-split ablation uninformative.

    Bins cohort_sizes into up to 4 quantile-based strata computed from the
    actual data (adapts to whatever cohort-size distribution a category has,
    rather than fixed thresholds that might not fit every category), then
    runs StratifiedKFold on the bin labels. Falls back to fewer bins, and
    ultimately to a single stratum (plain KFold behavior), if the requested
    bin count would leave any stratum with fewer members than n_splits —
    StratifiedKFold requires every class to have at least n_splits members.
    """
    sizes = cohort_sizes.fillna(1).to_numpy()
    n = len(sizes)

    strata = np.zeros(n, dtype=int)
    for n_bins in (4, 3, 2):
        try:
            candidate = pd.qcut(sizes, q=n_bins, labels=False, duplicates="drop")
        except ValueError:
            continue
        if candidate is None:
            continue
        candidate = np.asarray(candidate)
        counts = pd.Series(candidate).value_counts()
        if len(counts) > 1 and (counts >= n_splits).all():
            strata = candidate
            break

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = np.empty(n, dtype=int)
    for fold_idx, (_, test_idx) in enumerate(skf.split(np.zeros(n), strata)):
        folds[test_idx] = fold_idx
    return folds
