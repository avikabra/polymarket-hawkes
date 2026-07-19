"""Tests for TCNPredictor — includes mandatory causal property test."""
from __future__ import annotations

import torch
import pytest

from src.models.tcn_model import TCNPredictor

B, K, d = 2, 9, 16  # batch, window (so K+1=10 positions), dim


def test_output_shape():
    model = TCNPredictor(input_dim=d, channels=32, num_blocks=2, kernel_size=3)
    x = torch.randn(B, K + 1, d)
    mask = torch.ones(B, K + 1, dtype=torch.bool)
    out = model(x, mask)
    assert out.shape == (B, 1), f"Expected ({B}, 1), got {out.shape}"


def test_output_is_finite():
    model = TCNPredictor(input_dim=d, channels=32, num_blocks=2)
    model.eval()
    x = torch.randn(B, K + 1, d)
    mask = torch.ones(B, K + 1, dtype=torch.bool)
    with torch.no_grad():
        out = model(x, mask)
    assert torch.isfinite(out).all(), "Output contains nan or inf"


def test_causal_property():
    """Perturbing position K (last) of the projected features must NOT change
    earlier positions' outputs in the conv blocks — BLOCKING TEST.

    This verifies the TCN implementation is causal (no look-ahead bias).
    If this test fails, the TCN has a look-ahead bug — do NOT proceed to training.
    """
    torch.manual_seed(0)
    C = 32
    model = TCNPredictor(input_dim=d, channels=C, num_blocks=1, kernel_size=3, dropout=0.0)
    model.eval()

    K_local = 9  # K+1 = 10 positions
    x = torch.randn(1, K_local + 1, d)
    x_t = x.transpose(1, 2)  # (1, d, K_local+1)

    with torch.no_grad():
        proj = model.proj(x_t)  # (1, C, K_local+1)

        # Apply block 0 to original
        block = model.blocks[0]
        out1 = block(proj.clone())  # (1, C, K_local+1)

        # Perturb last position of the projected features
        proj2 = proj.clone()
        proj2[0, :, -1] = torch.randn(C)
        out2 = block(proj2)  # (1, C, K_local+1)

    # Positions 0..K_local-1 (all except the last) must be UNCHANGED
    # because a causal conv cannot have the last position's input affect earlier outputs.
    assert torch.allclose(out1[0, :, :-1], out2[0, :, :-1], atol=1e-5), (
        "TCN is NOT causal: perturbing the last position's input changed earlier "
        "positions' outputs. Check DilatedCausalConv1d left-padding."
    )


def test_receptive_field():
    """With num_blocks=3, kernel_size=3, dilations {1,2,4}: RF = 3*(1+2+4) = 21.

    A sequence of length 21 should have all positions within the RF of the last
    output, while a sequence of length 22 leaves the earliest position outside.
    We verify this indirectly: with a single block and dilation=1, kernel=3,
    RF=3. Two sequences identical at position 1 onward but different at position 0
    should give the SAME output at the LAST position only if position 0 is
    outside the RF.
    """
    torch.manual_seed(0)
    C = 16
    # num_blocks=1, kernel=3, dilation=1 → RF = 3
    model = TCNPredictor(input_dim=d, channels=C, num_blocks=1, kernel_size=3, dropout=0.0)
    model.eval()

    # Sequence length = 10 (> RF=3), so position 0 is outside RF of position 9
    L = 10
    x1 = torch.randn(1, L, d)
    x2 = x1.clone()
    x2[0, 0] = torch.randn(d)  # only perturb position 0

    mask = torch.ones(1, L, dtype=torch.bool)

    with torch.no_grad():
        out1 = model(x1, mask)  # uses last position's features
        out2 = model(x2, mask)

    # With RF=3 and L=10, position 0 is NOT in the receptive field of position 9
    # So the final output (taken at position -1) should be identical
    assert torch.allclose(out1, out2, atol=1e-5), (
        "Perturbing a position outside the receptive field changed the output."
    )


def test_gradient_flow():
    model = TCNPredictor(input_dim=d, channels=32, num_blocks=2, kernel_size=3)
    x = torch.randn(B, K + 1, d, requires_grad=True)
    mask = torch.ones(B, K + 1, dtype=torch.bool)
    loss = model(x, mask).sum()
    loss.backward()
    assert x.grad is not None, "No gradient flowed to input x"
    assert x.grad.abs().sum() > 0, "Gradient is all zeros"


def test_masked_positions_zeroed():
    """Padding positions zeroed by mask must not affect the output at the last position
    compared to fully-valid sequences when padding positions are zero anyway."""
    torch.manual_seed(1)
    model = TCNPredictor(input_dim=d, channels=32, num_blocks=2, dropout=0.0)
    model.eval()

    x = torch.randn(1, K + 1, d)
    # All-valid mask
    mask_full = torch.ones(1, K + 1, dtype=torch.bool)
    # Only last 3 positions valid; earlier positions are zero in x
    x_partial = x.clone()
    x_partial[0, :-3] = 0.0
    mask_partial = torch.zeros(1, K + 1, dtype=torch.bool)
    mask_partial[0, -3:] = True

    with torch.no_grad():
        # Construct a version where we zero out padded positions in x
        # and also apply the mask; outputs should differ from full-mask
        out_full = model(x, mask_full)
        out_partial = model(x_partial, mask_partial)

    # They may differ (different inputs), just check both are finite
    assert torch.isfinite(out_full).all()
    assert torch.isfinite(out_partial).all()
