"""Training loop with early stopping and checkpoint management."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from src.training.forward import batch_forward


class Trainer:
    """Train a sequence model with early stopping on val MSE.

    Args:
        model: PyTorch module (LSTMPredictor / TransformerPredictor / TCNPredictor
               or any dict-accepting model for tests).
        optimizer: torch optimizer.
        scheduler: optional LR scheduler (stepped once per epoch after val).
        train_loader: DataLoader for training split.
        val_loader: DataLoader for validation split.
        checkpoint_path: file path to save best model checkpoint.
        patience: epochs without val improvement before early stopping.
        max_epochs: maximum training epochs.
        device: torch device string.
        clip_grad_norm: max gradient norm (disabled if <= 0).
        embedding: "shock" or "raw" — which embedding key to pull from each batch.
        meta: optional dict saved into checkpoint["config"] (e.g. K, hparams).
    """

    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: Any | None,
        train_loader: DataLoader,
        val_loader: DataLoader,
        checkpoint_path: str,
        patience: int = 15,
        max_epochs: int = 100,
        device: str = "cpu",
        clip_grad_norm: float = 1.0,
        embedding: str = "shock",
        meta: dict | None = None,
    ) -> None:
        torch.manual_seed(42)
        self.model = model
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.checkpoint_path = Path(checkpoint_path)
        self.patience = patience
        self.max_epochs = max_epochs
        self.device = torch.device(device)
        self.clip_grad_norm = clip_grad_norm
        self.embedding = embedding
        self.meta: dict = meta or {}

        self.model.to(self.device)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    def train(self) -> dict:
        """Run the full training loop.

        Returns:
            dict with keys: best_val_mse, best_epoch,
            train_history (list of {epoch, train_mse, val_mse}).
        """
        best_val_mse = float("inf")
        best_epoch = 0
        no_improve = 0
        history: list[dict] = []

        for epoch in range(1, self.max_epochs + 1):
            train_mse = self._train_epoch()
            val_mse = self._val_epoch()

            if self.scheduler is not None:
                self.scheduler.step()

            history.append({"epoch": epoch, "train_mse": train_mse, "val_mse": val_mse})

            if val_mse < best_val_mse:
                best_val_mse = val_mse
                best_epoch = epoch
                no_improve = 0
                torch.save(
                    {
                        "epoch": epoch,
                        "model_state_dict": self.model.state_dict(),
                        "val_mse": val_mse,
                        "config": self.meta,
                    },
                    self.checkpoint_path,
                )
            else:
                no_improve += 1
                if no_improve >= self.patience:
                    # Restore best checkpoint
                    ckpt = torch.load(self.checkpoint_path, map_location=self.device, weights_only=True)
                    self.model.load_state_dict(ckpt["model_state_dict"])
                    break

        return {
            "best_val_mse": best_val_mse,
            "best_epoch": best_epoch,
            "train_history": history,
        }

    def _train_epoch(self) -> float:
        """Run one training epoch. Returns mean MSE over batches."""
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        for batch in self.train_loader:
            self.optimizer.zero_grad()
            y = batch["y_logit_6h"].to(self.device)
            preds = batch_forward(self.model, batch, self.device, self.embedding).squeeze(-1)  # (B,)
            loss = F.mse_loss(preds, y)
            loss.backward()
            if self.clip_grad_norm > 0:
                nn.utils.clip_grad_norm_(self.model.parameters(), self.clip_grad_norm)
            self.optimizer.step()
            total_loss += loss.item()
            n_batches += 1

        return total_loss / max(n_batches, 1)

    def _val_epoch(self) -> float:
        """Run one validation pass. Returns mean MSE over batches."""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        with torch.no_grad():
            for batch in self.val_loader:
                y = batch["y_logit_6h"].to(self.device)
                preds = batch_forward(self.model, batch, self.device, self.embedding).squeeze(-1)  # (B,)
                loss = F.mse_loss(preds, y)
                total_loss += loss.item()
                n_batches += 1

        return total_loss / max(n_batches, 1)
