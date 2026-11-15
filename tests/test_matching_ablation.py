"""Tests for src/analysis/matching_ablation.py's correlation helper — the pure
statistic scripts/09b_matching_ablation.py reports (novel_math_design.md Thread 1
"Validation (Q3) — REQUIRED, not optional"). Synthetic scores/reactions only; no
matches.db or bars data needed.
"""

import math

import pandas as pd
import pytest

from src.analysis.matching_ablation import compute_score_reaction_correlations


def test_perfect_monotonic_score_gives_rho_one():
    df = pd.DataFrame({
        "embedding_score": [0.1, 0.2, 0.3, 0.4, 0.5],
        "joint_score": [0.1, 0.2, 0.3, 0.4, 0.5],
        "realized_abs_y_logit_24h": [0.01, 0.02, 0.03, 0.04, 0.05],
    })
    result = compute_score_reaction_correlations(df)
    assert not result["degenerate"]
    assert result["embedding_rho"] == pytest.approx(1.0)
    assert result["joint_rho"] == pytest.approx(1.0)
    assert result["n_used"] == 5


def test_inversely_monotonic_score_gives_rho_negative_one():
    df = pd.DataFrame({
        "embedding_score": [0.5, 0.4, 0.3, 0.2, 0.1],
        "joint_score": [0.5, 0.4, 0.3, 0.2, 0.1],
        "realized_abs_y_logit_24h": [0.01, 0.02, 0.03, 0.04, 0.05],
    })
    result = compute_score_reaction_correlations(df)
    assert result["embedding_rho"] == pytest.approx(-1.0)
    assert result["joint_rho"] == pytest.approx(-1.0)


def test_joint_score_wins_when_it_tracks_reaction_better():
    """Synthetic case with a known winner: joint_score is a perfect monotonic
    transform of the realized reaction; embedding_score is unrelated (constant
    noise pattern uncorrelated with rank order)."""
    df = pd.DataFrame({
        "embedding_score": [0.5, 0.1, 0.9, 0.3, 0.5, 0.2],
        "joint_score":     [0.10, 0.15, 0.20, 0.25, 0.30, 0.35],
        "realized_abs_y_logit_24h": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06],
    })
    result = compute_score_reaction_correlations(df)
    assert result["joint_rho"] == pytest.approx(1.0)
    assert abs(result["joint_rho"]) > abs(result["embedding_rho"])


def test_rows_with_missing_realized_reaction_are_dropped():
    df = pd.DataFrame({
        "embedding_score": [0.1, 0.2, 0.3, 0.4, 0.5],
        "joint_score": [0.1, 0.2, 0.3, 0.4, 0.5],
        "realized_abs_y_logit_24h": [0.01, None, 0.03, None, 0.05],
    })
    result = compute_score_reaction_correlations(df)
    assert result["n_used"] == 3
    assert result["n_total"] == 5
    assert not result["degenerate"]


def test_all_missing_realized_reaction_is_degenerate():
    df = pd.DataFrame({
        "embedding_score": [0.1, 0.2, 0.3],
        "joint_score": [0.1, 0.2, 0.3],
        "realized_abs_y_logit_24h": [None, None, None],
    })
    result = compute_score_reaction_correlations(df)
    assert result["degenerate"]
    assert result["n_used"] == 0
    assert math.isnan(result["embedding_rho"])
    assert math.isnan(result["joint_rho"])


def test_too_few_rows_is_degenerate():
    df = pd.DataFrame({
        "embedding_score": [0.1, 0.2],
        "joint_score": [0.1, 0.2],
        "realized_abs_y_logit_24h": [0.01, 0.02],
    })
    result = compute_score_reaction_correlations(df)
    assert result["degenerate"]


def test_all_tied_realized_values_is_degenerate():
    """Every reaction identical -> rank correlation is undefined/trivial."""
    df = pd.DataFrame({
        "embedding_score": [0.1, 0.5, 0.9, 0.3],
        "joint_score": [0.2, 0.4, 0.6, 0.8],
        "realized_abs_y_logit_24h": [0.02, 0.02, 0.02, 0.02],
    })
    result = compute_score_reaction_correlations(df)
    assert result["degenerate"]
