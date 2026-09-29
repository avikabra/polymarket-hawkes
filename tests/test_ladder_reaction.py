"""Tests for src/analysis/ladder_reaction.py."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.ladder_reaction import (
    build_ladder_cohorts,
    compute_ladder_adjusted_reactions,
)


def _row(
    group_id="g1",
    end_at="2026-01-01T00:00:00+00:00",
    strike_price=None,
    strike_direction=None,
    y_24h=None,
    valid_24h=False,
    volume_24h_usdc=1000.0,
    **extra,
) -> dict:
    row = {
        "group_id": group_id,
        "end_at": end_at,
        "strike_price": strike_price,
        "strike_direction": strike_direction,
        "y_logit_24h": y_24h,
        "valid_24h": valid_24h,
        "volume_24h_usdc": volume_24h_usdc,
    }
    row.update(extra)
    return row


# (a) Synthetic 5-strike "below" cohort with one noisy outlier ---------------

def test_isotonic_corrects_monotone_below_cohort_with_outlier():
    # strike_direction="below" -> P(price below strike) increases with strike.
    # True underlying curve is increasing; strike 30's raw value is a
    # deliberately noisy outlier that violates monotonicity vs. its neighbors.
    strikes = [10, 20, 30, 40, 50]
    raw = [-1.0, -0.5, -2.0, 0.5, 1.0]  # -2.0 at strike 30 is the outlier
    rows = [
        _row(strike_price=s, strike_direction="below", y_24h=y, valid_24h=True)
        for s, y in zip(strikes, raw)
    ]
    df = pd.DataFrame(rows)

    out = compute_ladder_adjusted_reactions(df, window_hours=[24])
    out = out.sort_values("strike_price")

    corrected = out["y_logit_24h_ladder"].to_numpy()
    # Monotone non-decreasing in strike_price.
    assert np.all(np.diff(corrected) >= -1e-9)

    # The outlier's corrected value moved toward its neighbors: closer to a
    # smooth curve than the raw noisy value was. Compare distance from the
    # linear interpolation of its neighbors (strike 20 and strike 40 raw).
    neighbor_interp = (raw[1] + raw[3]) / 2  # (-0.5 + 0.5) / 2 = 0.0
    raw_outlier = raw[2]
    corrected_outlier = out.loc[out["strike_price"] == 30, "y_logit_24h_ladder"].iloc[0]
    assert abs(corrected_outlier - neighbor_interp) < abs(raw_outlier - neighbor_interp)

    # All 5 members were used in the fit.
    assert (out["ladder_n_members_used_24h"] == 5).all()


# (b) Singleton cohort ---------------------------------------------------

def test_singleton_cohort_is_unchanged_passthrough():
    df = pd.DataFrame([
        _row(strike_price=25.0, strike_direction="below", y_24h=0.42, valid_24h=True),
    ])

    out = compute_ladder_adjusted_reactions(df, window_hours=[24])

    assert out["y_logit_24h_ladder"].iloc[0] == pytest.approx(0.42)
    assert out["ladder_n_members_used_24h"].iloc[0] == 1


def test_corporate_event_missing_strike_info_is_singleton():
    """Rows with no strike_price/strike_direction (e.g. corporate_event) get
    their own singleton cohort — no error, explicit no-op passthrough."""
    df = pd.DataFrame([
        _row(group_id="g_corp", strike_price=None, strike_direction=None,
             y_24h=0.1, valid_24h=True),
        _row(group_id="g_corp", strike_price=None, strike_direction=None,
             y_24h=0.9, valid_24h=True),
    ])

    cohorts = build_ladder_cohorts(df)
    # Two rows sharing the same (missing) group info must NOT be pooled —
    # each gets its own singleton, keyed by row index.
    assert cohorts.iloc[0] != cohorts.iloc[1]

    out = compute_ladder_adjusted_reactions(df, window_hours=[24])
    assert out["y_logit_24h_ladder"].tolist() == pytest.approx([0.1, 0.9])
    assert (out["ladder_n_members_used_24h"] == 1).all()


# (c) No-arbitrage direction test -----------------------------------------

def test_above_direction_violation_is_corrected_non_increasing():
    """strike_direction='above' means P(price above X) decreases with X —
    increasing=False. A raw input where a HIGHER strike has a LARGER
    reaction than a LOWER strike is a real monotonicity violation; the
    corrected curve must come out non-increasing. This is the test that
    would catch a backwards `increasing=` bug (it would instead assert/allow
    a non-decreasing corrected curve)."""
    strikes = [10, 20, 30]
    raw = [0.1, 0.2, 0.9]  # increasing raw values — violates "above" ordering
    rows = [
        _row(strike_price=s, strike_direction="above", y_24h=y, valid_24h=True)
        for s, y in zip(strikes, raw)
    ]
    df = pd.DataFrame(rows)

    out = compute_ladder_adjusted_reactions(df, window_hours=[24])
    out = out.sort_values("strike_price")
    corrected = out["y_logit_24h_ladder"].to_numpy()

    # Raw is strictly increasing, so it already satisfies "non-decreasing" —
    # a backwards `increasing=` bug (True instead of False here) would treat
    # it as already monotone and leave it completely unchanged. The correct
    # non-increasing constraint instead forces PAVA to pool every point into
    # one flat (weighted-mean) block, since the whole sequence violates it.
    assert np.all(np.diff(corrected) <= 1e-9)  # non-increasing (near-flat)
    assert not np.allclose(corrected, np.array(raw))


# (d) Invalid siblings excluded from the fit -------------------------------

def test_invalid_members_excluded_from_fit_but_get_own_passthrough():
    strikes = [10, 20, 30, 40]
    raw = [-1.0, 0.0, 999.0, 1.0]  # strike 30 is invalid — would corrupt the fit
    valid = [True, True, False, True]
    rows = [
        _row(strike_price=s, strike_direction="below", y_24h=y, valid_24h=v)
        for s, y, v in zip(strikes, raw, valid)
    ]
    df = pd.DataFrame(rows)

    out = compute_ladder_adjusted_reactions(df, window_hours=[24])
    out = out.sort_values("strike_price")

    invalid_row = out[out["strike_price"] == 30].iloc[0]
    # Invalid row keeps its own (raw, un-fitted) value and isn't counted as
    # used in anyone's fit.
    assert invalid_row["y_logit_24h_ladder"] == pytest.approx(999.0)
    assert invalid_row["ladder_n_members_used_24h"] == 0

    # The 3 valid rows were fit together (not corrupted by the 999.0 outlier)
    # and are monotone non-decreasing among themselves.
    valid_out = out[out["strike_price"] != 30]
    assert (valid_out["ladder_n_members_used_24h"] == 3).all()
    corrected = valid_out["y_logit_24h_ladder"].to_numpy()
    assert np.all(np.diff(corrected) >= -1e-9)
    assert np.all(corrected < 100)  # nowhere near the excluded 999.0 outlier


# Generic multi-window handling ---------------------------------------------

def test_generic_over_multiple_windows_not_hardcoded_to_24h():
    strikes = [10, 20, 30]
    rows = [
        _row(
            strike_price=s, strike_direction="below",
            y_24h=float(i), valid_24h=True,
            y_logit_1h=float(i) * 0.1, valid_1h=True,
            y_logit_6h=None, valid_6h=False,
        )
        for i, s in enumerate(strikes)
    ]
    df = pd.DataFrame(rows)

    out = compute_ladder_adjusted_reactions(df, window_hours=[1, 6, 24])

    assert "y_logit_1h_ladder" in out.columns
    assert "y_logit_6h_ladder" in out.columns
    assert "y_logit_24h_ladder" in out.columns
    assert "ladder_n_members_used_1h" in out.columns
    assert "ladder_n_members_used_6h" in out.columns
    assert "ladder_n_members_used_24h" in out.columns

    # 6h: all invalid -> pure passthrough (all null), n_used all 0.
    assert out["y_logit_6h_ladder"].isna().all()
    assert (out["ladder_n_members_used_6h"] == 0).all()

    # 1h: all valid -> real joint fit across all 3 members.
    assert (out["ladder_n_members_used_1h"] == 3).all()
