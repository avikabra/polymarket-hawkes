"""Tests for Trainer class using a tiny synthetic linear model."""
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

import pytest

from src.training.trainer import Trainer


# ---- Minimal model that accepts a dict batch (matching Trainer contract) ----

class _TinyLinearModel(nn.Module):
    """A single nn.Linear that reads 'embedding' from the batch dict."""

    def __init__(self, in_dim: int = 8):
        super().__init__()
        self.fc = nn.Linear(in_dim, 1)

    def forward(self, batch: dict) -> torch.Tensor:
        x = batch["embedding"]
        return self.fc(x)  # (B, 1)


# ---- Synthetic DataLoader helpers ----

def _make_loader(n: int = 64, d: int = 8, seed: int = 0) -> DataLoader:
    """Create a DataLoader that yields dict batches with 'embedding' and 'y_logit_6h'."""
    g = torch.Generator()
    g.manual_seed(seed)
    X = torch.randn(n, d, generator=g)
    # y = X @ w + noise (non-trivial linear signal so loss can decrease)
    w = torch.randn(d, 1, generator=g)
    y = (X @ w).squeeze(-1) + 0.01 * torch.randn(n, generator=g)

    class _DictDataset(torch.utils.data.Dataset):
        def __init__(self, X, y):
            self.X = X
            self.y = y

        def __len__(self):
            return len(self.X)

        def __getitem__(self, i):
            return {"embedding": self.X[i], "y_logit_6h": self.y[i]}

    ds = _DictDataset(X, y)
    return DataLoader(ds, batch_size=16, shuffle=True)


class _ConstantLossLoader:
    """A fake DataLoader that yields the same high-loss batch on every iteration."""

    def __init__(self, d: int = 8, loss_value: float = 1e6, n_batches: int = 2):
        self._d = d
        self._loss = loss_value
        self._n = n_batches

    def __iter__(self):
        for _ in range(self._n):
            # y_pred will be near 0 (untrained model), y will be huge → high MSE
            yield {
                "embedding": torch.zeros(4, self._d),
                "y_logit_6h": torch.full((4,), self._loss),
            }


def _make_trainer(
    model: nn.Module,
    train_loader,
    val_loader,
    ckpt_path: str,
    patience: int = 3,
    max_epochs: int = 20,
) -> Trainer:
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    return Trainer(
        model=model,
        optimizer=optimizer,
        scheduler=None,
        train_loader=train_loader,
        val_loader=val_loader,
        checkpoint_path=ckpt_path,
        patience=patience,
        max_epochs=max_epochs,
        device="cpu",
        clip_grad_norm=1.0,
    )


# ---- Tests ----

def test_loss_decreases(tmp_path):
    """Training loss at epoch 5 should be lower than at epoch 1."""
    model = _TinyLinearModel(in_dim=8)
    train_loader = _make_loader(n=128, d=8, seed=1)
    val_loader = _make_loader(n=32, d=8, seed=2)
    ckpt = str(tmp_path / "tiny.pt")

    trainer = _make_trainer(model, train_loader, val_loader, ckpt, patience=20, max_epochs=10)
    outcome = trainer.train()

    history = outcome["train_history"]
    assert len(history) >= 5, "Expected at least 5 epochs of history"
    mse_epoch1 = history[0]["train_mse"]
    mse_epoch5 = history[4]["train_mse"]
    assert mse_epoch5 < mse_epoch1, (
        f"Expected loss to decrease: epoch1={mse_epoch1:.4f}, epoch5={mse_epoch5:.4f}"
    )


def test_checkpoint_saved(tmp_path):
    """Checkpoint file must exist after training."""
    model = _TinyLinearModel(in_dim=8)
    train_loader = _make_loader(n=64, d=8, seed=3)
    val_loader = _make_loader(n=16, d=8, seed=4)
    ckpt = str(tmp_path / "subdir" / "model.pt")

    trainer = _make_trainer(model, train_loader, val_loader, ckpt, patience=20, max_epochs=3)
    trainer.train()

    assert Path(ckpt).exists(), f"Checkpoint not found at {ckpt}"
    # Verify it can be loaded
    loaded = torch.load(ckpt, map_location="cpu", weights_only=True)
    assert "model_state_dict" in loaded


def test_early_stopping(tmp_path):
    """With a val loader that always returns high loss, training stops before max_epochs."""
    patience = 3
    max_epochs = 50

    model = _TinyLinearModel(in_dim=8)
    train_loader = _make_loader(n=64, d=8, seed=5)
    val_loader = _ConstantLossLoader(d=8, loss_value=1e6, n_batches=2)
    ckpt = str(tmp_path / "early_stop.pt")

    trainer = _make_trainer(
        model, train_loader, val_loader, ckpt,
        patience=patience, max_epochs=max_epochs
    )
    outcome = trainer.train()

    n_epochs_run = len(outcome["train_history"])
    # With constant high val loss, should stop at patience+1 epochs (1 good + patience bad)
    # Allow a small buffer in case the first epoch is counted as "improvement"
    assert n_epochs_run < max_epochs, (
        f"Early stopping did not trigger: ran {n_epochs_run}/{max_epochs} epochs"
    )
