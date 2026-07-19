"""Continuous-time positional encoding for irregular news arrival intervals.

Encodes Δt (time gap normalized to [0,1]) rather than integer position index.
Formula (per §0.3 of the plan):
  PE(Δt, 2k)   = sin(Δt / 10000^{2k / d_model})
  PE(Δt, 2k+1) = cos(Δt / 10000^{2k / d_model})
"""
from __future__ import annotations
import torch
import torch.nn as nn

class ContinuousTimePositionalEncoding(nn.Module):
    """
    Input:  delta_t: (batch, seq_len) — time gaps normalized to [0, 1]
    Output: (batch, seq_len, d_model)
    """
    def __init__(self, d_model: int, tau_max_days: float = 30.0):
        super().__init__()
        self.d_model = d_model
        self.tau_max_days = tau_max_days
        # Precompute 1 / 10000^{2k/d_model} for k = 0..d_model//2-1
        dim = d_model // 2
        div_term = torch.pow(
            torch.tensor(10000.0),
            torch.arange(0, dim, dtype=torch.float32) * 2.0 / d_model,
        )
        self.register_buffer("div_term", div_term)  # (dim,)

    def forward(self, delta_t: torch.Tensor) -> torch.Tensor:
        # delta_t: (B, S)
        # Result:  (B, S, d_model)
        B, S = delta_t.shape
        dt = delta_t.unsqueeze(-1)  # (B, S, 1)
        # angles: (B, S, dim)
        angles = dt / self.div_term  # broadcasts over dim
        enc = torch.cat([torch.sin(angles), torch.cos(angles)], dim=-1)  # (B, S, d_model or d_model+1 if odd)
        return enc[:, :, : self.d_model]  # trim if d_model is odd
