"""Tests for the Thread 1 weight-tuning primitives (src/analysis/matching_ablation.py's
compute_single_score_correlation / match_quality_score / grid_search_weights) used by
scripts/09c_tune_matching_weights.py. Synthetic scores/reactions only; no matches.db,
bars data, or held-out split machinery needed — that I/O lives in the script, not here.
"""

import math

import pandas as pd
import pytest

from src.analysis.matching_ablation import (
    compute_single_score_correlation,
    grid_search_weights,
    match_quality_score,
)
from src.matching.joint_verifier import _logit, _sigmoid


def test_single_score_correlation_perfect_positive():
    scores = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
    reactions = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
    result = compute_single_score_correlation(scores, reactions)
    assert not result["degenerate"]
    assert result["rho"] == pytest.approx(1.0)
    assert result["n_used"] == 5


def test_single_score_correlation_drops_nulls():
    scores = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
    reactions = pd.Series([0.01, None, 0.03, None, 0.05])
    result = compute_single_score_correlation(scores, reactions)
    assert result["n_used"] == 3
    assert not result["degenerate"]


def test_single_score_correlation_degenerate_on_too_few_rows():
    result = compute_single_score_correlation(pd.Series([0.1, 0.2]), pd.Series([0.01, 0.02]))
    assert result["degenerate"]
    assert math.isnan(result["rho"])


def test_single_score_correlation_degenerate_on_tied_reactions():
    scores = pd.Series([0.1, 0.5, 0.9, 0.3])
    reactions = pd.Series([0.02, 0.02, 0.02, 0.02])
    result = compute_single_score_correlation(scores, reactions)
    assert result["degenerate"]


def test_match_quality_score_matches_joint_verifier_formula():
    """match_quality_score must reproduce joint_verifier.py's exact per-pair
    formula — verified here against the same _logit/_sigmoid it imports, for
    one hand-computed point, so a future refactor of either can't silently
    diverge them."""
    emb = pd.Series([0.8])
    liq = pd.Series([1.5])
    w1, w2 = 2.0, 0.5
    got = match_quality_score(emb, liq, w1, w2).iloc[0]
    expected = _sigmoid(w1 * _logit(0.8) + w2 * 1.5)
    assert got == pytest.approx(expected)


def test_match_quality_score_zero_weight_ignores_that_signal():
    """w2=0 must make liquidity_z irrelevant — pure embedding-driven score."""
    emb = pd.Series([0.7, 0.7])
    liq = pd.Series([-5.0, 5.0])  # wildly different liquidity, should not matter
    scores = match_quality_score(emb, liq, w1=1.0, w2=0.0)
    assert scores.iloc[0] == pytest.approx(scores.iloc[1])


def test_grid_search_finds_weights_that_recover_a_known_signal():
    """Construct realized reactions as a known function of liquidity_z alone
    (embedding_score is pure noise, uncorrelated with the outcome). The grid
    search must favor a high w2 (liquidity-driven) combination over a
    liquidity-blind one (w2=0) — sanity-checks the search actually explores
    and ranks the grid rather than just returning some fixed point."""
    n = 30
    liquidity_z = pd.Series([float(i) for i in range(n)])
    embedding_score = pd.Series([0.5 + 0.01 * ((-1) ** i) for i in range(n)])  # near-constant noise
    realized = pd.Series([float(i) for i in range(n)])  # perfectly monotonic in liquidity_z

    results = grid_search_weights(
        embedding_score, liquidity_z, realized, weight_grid=[0.0, 1.0, 3.0],
    )
    best = results.iloc[0]
    assert not bool(best["degenerate"])
    assert best["w2"] > 0.0, "best weight combination should lean on the liquidity signal"
    assert best["rho"] == pytest.approx(1.0, abs=1e-6)


def test_grid_search_returns_one_row_per_combination():
    n = 10
    embedding_score = pd.Series([0.1 * i for i in range(1, n + 1)])
    liquidity_z = pd.Series([0.2 * i for i in range(1, n + 1)])
    realized = pd.Series([0.01 * i for i in range(1, n + 1)])
    grid = [0.0, 1.0, 2.0]
    results = grid_search_weights(embedding_score, liquidity_z, realized, grid)
    assert len(results) == len(grid) * len(grid)
    assert set(results["w1"].unique()) == set(grid)
    assert set(results["w2"].unique()) == set(grid)
