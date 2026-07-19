"""TCN predictor with dilated causal convolutions (Bai et al. 2018, §2.4)."""
from __future__ import annotations
import torch
import torch.nn as nn
import torch.nn.functional as F

class DilatedCausalConv1d(nn.Module):
    """Causal dilated 1D conv with manual left-padding (no look-ahead)."""
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int):
        super().__init__()
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, dilation=dilation, padding=0)
        self._pad = (kernel_size - 1) * dilation

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, L)
        x = F.pad(x, (self._pad, 0))
        return self.conv(x)

class TCNResidualBlock(nn.Module):
    def __init__(self, channels: int, kernel_size: int, dilation: int, dropout: float):
        super().__init__()
        self.conv1 = DilatedCausalConv1d(channels, channels, kernel_size, dilation)
        self.norm1 = nn.LayerNorm(channels)
        self.conv2 = DilatedCausalConv1d(channels, channels, kernel_size, dilation)
        self.norm2 = nn.LayerNorm(channels)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, L)
        residual = x
        out = self.conv1(x)
        # LayerNorm expects (B, L, C) — transpose
        out = self.norm1(out.transpose(1, 2)).transpose(1, 2)
        out = F.relu(out)
        out = self.drop(out)
        out = self.conv2(out)
        out = self.norm2(out.transpose(1, 2)).transpose(1, 2)
        out = F.relu(out)
        return out + residual

class TCNPredictor(nn.Module):
    def __init__(
        self,
        input_dim: int,
        channels: int = 256,
        num_blocks: int = 3,
        kernel_size: int = 3,
        dropout: float = 0.1,
        n_categories: int = 0,
    ):
        super().__init__()
        # Input projection (channels-first)
        self.proj = nn.Conv1d(input_dim, channels, kernel_size=1)
        self.blocks = nn.ModuleList([
            TCNResidualBlock(channels, kernel_size, dilation=2 ** b, dropout=dropout)
            for b in range(num_blocks)
        ])
        self.drop = nn.Dropout(dropout)
        mlp_in = channels + n_categories
        self.mlp = nn.Sequential(
            nn.Linear(mlp_in, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )
        self.n_categories = n_categories

    def forward(
        self,
        x: torch.Tensor,  # (B, K+1, d)
        mask: torch.Tensor,  # (B, K+1) bool; True=valid
        category_onehot: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # Transpose to channels-first: (B, d, K+1)
        x = x.transpose(1, 2)
        x = self.proj(x)  # (B, C, K+1)
        for block in self.blocks:
            x = block(x)
        # Zero out padded positions to prevent leakage
        valid = mask.unsqueeze(1).float()  # (B, 1, K+1)
        x = x * valid
        # Take last valid position's output
        # Use the last time step (position K, 0-indexed) which is always the target article
        last = x[:, :, -1]  # (B, C)
        last = self.drop(last)
        if self.n_categories > 0 and category_onehot is not None:
            last = torch.cat([last, category_onehot.float()], dim=-1)
        return self.mlp(last)  # (B, 1)
