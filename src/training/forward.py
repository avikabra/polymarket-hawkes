"""Shared forward-pass adapter and device selection for all neural architectures.

This module centralises three concerns that were previously scattered or broken:
  1. Device selection (cuda → mps → cpu, or explicit pref).
  2. Unpacking a batch dict into the correct per-model tensor call.
  3. Routing the embedding key (shock_embeddings vs raw_embeddings) so that
     --embedding raw runs use the correct input everywhere.
"""
from __future__ import annotations

import torch
import torch.nn as nn


def select_device(pref: str = "auto") -> torch.device:
    """Select the best available device.

    Args:
        pref: "auto"  → cuda > mps > cpu
              "cuda"  → force cuda (crashes if unavailable)
              "mps"   → force mps
              "cpu"   → force cpu
    """
    if pref == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():  # type: ignore[attr-defined]
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(pref)


def batch_forward(
    model: nn.Module,
    batch: dict,
    device: torch.device,
    embedding: str = "shock",
) -> torch.Tensor:
    """Call model.forward with the correct tensor arguments for this architecture.

    Selects `shock_embeddings` or `raw_embeddings` from the batch according to
    `embedding`, moves all required tensors to `device`, then dispatches to the
    correct forward signature.

    Supported model types (detected by isinstance):
      - LSTMPredictor:        forward(x, mask, lengths)
      - TransformerPredictor: forward(x, timestamps, mask)
      - TCNPredictor:         forward(x, mask)
      - anything else:        model(batch) — keeps test_trainer.py's tiny dict-model working

    If model is wrapped (e.g. nn.DataParallel), the inner model is inspected.

    Returns:
        Tensor of shape (B, 1).
    """
    from src.models.lstm_model import LSTMPredictor
    from src.models.transformer_model import TransformerPredictor
    from src.models.tcn_model import TCNPredictor

    # Unwrap DataParallel / DistributedDataParallel
    inner = model.module if hasattr(model, "module") else model

    emb_key = "shock_embeddings" if embedding == "shock" else "raw_embeddings"

    if isinstance(inner, LSTMPredictor):
        x = batch[emb_key].to(device)
        mask = batch["mask"].to(device)
        lengths = batch["lengths"].to(device)
        return model(x, mask, lengths)

    if isinstance(inner, TransformerPredictor):
        x = batch[emb_key].to(device)
        timestamps = batch["timestamps"].to(device)
        mask = batch["mask"].to(device)
        return model(x, timestamps, mask)

    if isinstance(inner, TCNPredictor):
        x = batch[emb_key].to(device)
        mask = batch["mask"].to(device)
        return model(x, mask)

    # Fallback: pass the whole batch dict (used in tests with tiny synthetic models)
    return model(batch)
