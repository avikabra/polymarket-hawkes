"""Tests for ContinuousTimePositionalEncoding."""
from __future__ import annotations

import torch
import pytest

from src.models.positional_encoding import ContinuousTimePositionalEncoding


def test_output_shape():
    pe = ContinuousTimePositionalEncoding(d_model=64)
    delta_t = torch.rand(3, 10)
    out = pe(delta_t)
    assert out.shape == (3, 10, 64), f"Expected (3, 10, 64), got {out.shape}"


def test_output_shape_various_d_models():
    """Output shape must match d_model exactly for even d_model values."""
    for d_model in (16, 32, 64):
        pe = ContinuousTimePositionalEncoding(d_model=d_model)
        delta_t = torch.rand(2, 5)
        out = pe(delta_t)
        assert out.shape == (2, 5, d_model), (
            f"Expected (2, 5, {d_model}), got {out.shape}"
        )


def test_deterministic():
    """Same input should always produce same output (no randomness)."""
    pe = ContinuousTimePositionalEncoding(d_model=32)
    dt = torch.rand(2, 5)
    out_a = pe(dt)
    out_b = pe(dt)
    assert torch.allclose(out_a, out_b), "Output is not deterministic"


def test_dt_zero_vs_nonzero_distinct():
    """PE(0) must differ from PE(0.5) — encoding must vary with Δt."""
    pe = ContinuousTimePositionalEncoding(d_model=32)
    dt_zero = torch.zeros(1, 1)
    dt_half = torch.full((1, 1), 0.5)
    out_zero = pe(dt_zero)
    out_half = pe(dt_half)
    assert not torch.allclose(out_zero, out_half, atol=1e-3), (
        "PE is identical for Δt=0 and Δt=0.5 — encoding is not time-varying."
    )


def test_output_is_finite():
    """Encoding values must be finite for any normalized input in [0, 1]."""
    pe = ContinuousTimePositionalEncoding(d_model=64)
    dt = torch.rand(4, 20)
    out = pe(dt)
    assert torch.isfinite(out).all(), "PE output contains nan or inf"


def test_output_bounded():
    """Sine/cosine encoding values must lie within [-1, 1]."""
    pe = ContinuousTimePositionalEncoding(d_model=128)
    dt = torch.rand(8, 16)
    out = pe(dt)
    assert out.abs().max().item() <= 1.0 + 1e-5, (
        f"PE value out of [-1,1]: max abs = {out.abs().max().item():.4f}"
    )


def test_batch_independence():
    """Each row of the batch must be encoded independently of other rows."""
    pe = ContinuousTimePositionalEncoding(d_model=32)
    dt1 = torch.rand(1, 6)
    dt2 = torch.rand(1, 6)
    dt_stacked = torch.cat([dt1, dt2], dim=0)  # (2, 6)

    out_single_1 = pe(dt1)  # (1, 6, 32)
    out_single_2 = pe(dt2)  # (1, 6, 32)
    out_batched = pe(dt_stacked)  # (2, 6, 32)

    assert torch.allclose(out_batched[0:1], out_single_1, atol=1e-6)
    assert torch.allclose(out_batched[1:2], out_single_2, atol=1e-6)
