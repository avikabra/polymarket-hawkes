"""Tests for src/training/forward.py — batch_forward dispatch and embedding selection.

TCNPredictor and TransformerPredictor are safe to construct on all platforms
(no orthogonal_ call in their __init__).  Tests that need LSTMPredictor are
skipped on Darwin because torch.nn.init.orthogonal_ segfaults on Intel Mac +
torch 2.2.x.  All tests run on Colab (Linux/CUDA) where training happens.
"""
from __future__ import annotations

import sys

import pytest
import torch
import torch.nn as nn

from src.models.tcn_model import TCNPredictor
from src.models.transformer_model import TransformerPredictor
from src.training.forward import batch_forward, select_device

D = 16
K = 3
B = 4

_SKIP_LSTM = pytest.mark.skipif(
    sys.platform == "darwin",
    reason="LSTMPredictor.orthogonal_ segfaults on Intel Mac + torch 2.2.x; run on Colab",
)


def _make_batch(d: int = D, k: int = K, batch_size: int = B) -> dict:
    """Synthetic batch matching ArticleSequenceDataset output schema."""
    seq_len = k + 1
    shock = torch.randn(batch_size, seq_len, d)
    raw = shock * 2.0 + 1.0   # deliberately different
    mask = torch.ones(batch_size, seq_len, dtype=torch.bool)
    return {
        "shock_embeddings": shock,
        "raw_embeddings": raw,
        "mask": mask,
        "lengths": torch.full((batch_size,), seq_len, dtype=torch.long),
        "timestamps": torch.rand(batch_size, seq_len),
        "y_logit_6h": torch.randn(batch_size),
    }


# ── Device selection ──────────────────────────────────────────────────────────

def test_select_device_cpu():
    d = select_device("cpu")
    assert d == torch.device("cpu")


def test_select_device_auto_returns_device():
    d = select_device("auto")
    assert isinstance(d, torch.device)


# ── TCN dispatch (safe on all platforms) ──────────────────────────────────────

def test_dispatch_tcn_shape():
    """batch_forward routes (x, mask) correctly to TCNPredictor."""
    model = TCNPredictor(input_dim=D, channels=16, num_blocks=1)
    model.eval()
    batch = _make_batch()
    out = batch_forward(model, batch, torch.device("cpu"), "shock")
    assert out.shape == (B, 1), f"Expected ({B},1), got {out.shape}"


def test_dispatch_tcn_finite():
    model = TCNPredictor(input_dim=D, channels=16, num_blocks=1)
    model.eval()
    out = batch_forward(model, _make_batch(), torch.device("cpu"), "shock")
    assert torch.isfinite(out).all()


# ── Transformer dispatch (safe on all platforms) ──────────────────────────────

def test_dispatch_transformer_shape():
    """batch_forward routes (x, timestamps, mask) correctly to TransformerPredictor."""
    model = TransformerPredictor(input_dim=D, d_model=16, nhead=2, num_layers=1, dim_feedforward=32)
    model.eval()
    out = batch_forward(model, _make_batch(), torch.device("cpu"), "shock")
    assert out.shape == (B, 1)


def test_dispatch_transformer_finite():
    model = TransformerPredictor(input_dim=D, d_model=16, nhead=2, num_layers=1, dim_feedforward=32)
    model.eval()
    out = batch_forward(model, _make_batch(), torch.device("cpu"), "shock")
    assert torch.isfinite(out).all()


# ── Embedding key selection (uses TCN, safe on all platforms) ─────────────────

def test_shock_vs_raw_differ():
    """--embedding raw must produce different outputs than --embedding shock."""
    model = TCNPredictor(input_dim=D, channels=16, num_blocks=1)
    model.eval()
    batch = _make_batch()
    device = torch.device("cpu")

    out_shock = batch_forward(model, batch, device, "shock")
    out_raw = batch_forward(model, batch, device, "raw")

    assert not torch.allclose(out_shock, out_raw), (
        "shock and raw outputs are identical — embedding key selection is broken"
    )


def test_raw_key_not_shock():
    """Poisoning shock_embeddings must not affect the raw run."""
    model = TCNPredictor(input_dim=D, channels=16, num_blocks=1)
    model.eval()
    batch = _make_batch()
    batch["shock_embeddings"] = torch.full_like(batch["shock_embeddings"], float("nan"))
    out = batch_forward(model, batch, torch.device("cpu"), "raw")
    assert torch.isfinite(out).all(), "raw forward used poisoned shock_embeddings"


# ── Dict-model fallback ───────────────────────────────────────────────────────

def test_dict_model_fallback():
    """Unrecognised models receive the full batch dict (keeps test_trainer.py working)."""
    class _DictModel(nn.Module):
        def forward(self, batch: dict) -> torch.Tensor:
            return batch["y_logit_6h"].unsqueeze(-1)

    out = batch_forward(_DictModel(), _make_batch(), torch.device("cpu"), "shock")
    assert out.shape == (B, 1)


# ── LSTM dispatch (skipped on Darwin) ────────────────────────────────────────

@_SKIP_LSTM
def test_dispatch_lstm_shape():
    """batch_forward routes (x, mask, lengths) correctly to LSTMPredictor."""
    from src.models.lstm_model import LSTMPredictor
    model = LSTMPredictor(input_dim=D, proj_dim=16, hidden_dim=16)
    model.eval()
    out = batch_forward(model, _make_batch(), torch.device("cpu"), "shock")
    assert out.shape == (B, 1)
    assert torch.isfinite(out).all()
