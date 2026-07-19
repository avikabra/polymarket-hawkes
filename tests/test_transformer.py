"""Tests for TransformerPredictor — includes mandatory mask polarity test."""
from __future__ import annotations

import torch
import pytest

from src.models.transformer_model import TransformerPredictor

B, K, d = 2, 4, 16  # batch, window (K+1=5 positions), dim


def test_output_shape():
    model = TransformerPredictor(input_dim=d, d_model=32, nhead=2, num_layers=1)
    x = torch.randn(B, K + 1, d)
    timestamps = torch.rand(B, K + 1)
    mask = torch.ones(B, K + 1, dtype=torch.bool)
    out = model(x, timestamps, mask)
    assert out.shape == (B, 1), f"Expected ({B}, 1), got {out.shape}"


def test_output_is_finite():
    model = TransformerPredictor(input_dim=d, d_model=32, nhead=2, num_layers=1)
    model.eval()
    x = torch.randn(B, K + 1, d)
    timestamps = torch.rand(B, K + 1)
    mask = torch.ones(B, K + 1, dtype=torch.bool)
    with torch.no_grad():
        out = model(x, timestamps, mask)
    assert torch.isfinite(out).all(), "Output contains nan or inf"


def test_mask_polarity():
    """Padding mask polarity must be correct: ~mask is passed to src_key_padding_mask.

    A model that incorrectly attends to padding positions will give DIFFERENT
    outputs when the padding content changes but the mask marks those positions
    as invalid. Correct implementation: output is IDENTICAL.
    """
    torch.manual_seed(0)
    model = TransformerPredictor(
        input_dim=d, d_model=32, nhead=2, num_layers=1, dropout=0.0
    )
    model.eval()

    # 2 valid positions (last 2), 3 padding positions (first 3)
    x1 = torch.zeros(1, K + 1, d)
    x2 = torch.randn(1, K + 1, d)  # different padding content

    # Keep the last 2 positions identical in both
    shared_valid = torch.randn(2, d)
    x1[0, -2:] = shared_valid
    x2[0, -2:] = shared_valid

    # mask: True = valid, False = padding
    mask = torch.zeros(1, K + 1, dtype=torch.bool)
    mask[0, -2:] = True  # last 2 positions are valid

    timestamps = torch.zeros(1, K + 1)

    with torch.no_grad():
        o1 = model(x1, timestamps, mask)
        o2 = model(x2, timestamps, mask)

    assert torch.allclose(o1, o2, atol=1e-5), (
        f"Transformer mask polarity is WRONG: output differs when padding content changes. "
        f"o1={o1.item():.6f}, o2={o2.item():.6f}. "
        f"Check that src_key_padding_mask receives ~mask (True=ignore)."
    )


def test_gradient_flow():
    model = TransformerPredictor(input_dim=d, d_model=32, nhead=2, num_layers=1)
    x = torch.randn(B, K + 1, d, requires_grad=True)
    timestamps = torch.rand(B, K + 1)
    mask = torch.ones(B, K + 1, dtype=torch.bool)
    loss = model(x, timestamps, mask).sum()
    loss.backward()
    assert x.grad is not None, "No gradient flowed to input x"
    assert x.grad.abs().sum() > 0, "Gradient is all zeros"


def test_all_valid_vs_some_valid_differ():
    """Output when all positions are valid should differ from when half are masked."""
    torch.manual_seed(2)
    model = TransformerPredictor(input_dim=d, d_model=32, nhead=2, num_layers=1, dropout=0.0)
    model.eval()

    x = torch.randn(1, K + 1, d)
    timestamps = torch.rand(1, K + 1)
    mask_all = torch.ones(1, K + 1, dtype=torch.bool)
    mask_half = torch.zeros(1, K + 1, dtype=torch.bool)
    mask_half[0, -(K + 1) // 2:] = True

    with torch.no_grad():
        out_all = model(x, timestamps, mask_all)
        out_half = model(x, timestamps, mask_half)

    # Different masking → different mean-pool → different outputs
    assert not torch.allclose(out_all, out_half, atol=1e-4), (
        "Output identical for all-valid and half-valid masks — likely mask not applied."
    )


def test_d_model_nhead_constraint():
    """d_model must be divisible by nhead; violation should raise AssertionError."""
    with pytest.raises(AssertionError):
        TransformerPredictor(input_dim=d, d_model=33, nhead=4, num_layers=1)
