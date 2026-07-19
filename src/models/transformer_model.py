"""Transformer predictor with continuous-time positional encoding (§2.3)."""
from __future__ import annotations
import torch
import torch.nn as nn
from src.models.positional_encoding import ContinuousTimePositionalEncoding

class TransformerPredictor(nn.Module):
    def __init__(
        self,
        input_dim: int,
        d_model: int = 256,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
        tau_max_days: float = 30.0,
        n_categories: int = 0,
    ):
        super().__init__()
        assert d_model % nhead == 0, f"d_model={d_model} must be divisible by nhead={nhead}"
        self.proj = nn.Linear(input_dim, d_model)
        self.norm = nn.LayerNorm(d_model)
        self.pe = ContinuousTimePositionalEncoding(d_model, tau_max_days)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        mlp_in = d_model + n_categories
        self.mlp = nn.Sequential(
            nn.Linear(mlp_in, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )
        self.n_categories = n_categories

    def forward(
        self,
        x: torch.Tensor,           # (B, K+1, d)
        timestamps: torch.Tensor,  # (B, K+1) delta_t normalized to [0,1]
        mask: torch.Tensor,        # (B, K+1) bool; True=valid
        category_onehot: torch.Tensor | None = None,
    ) -> torch.Tensor:
        z = self.norm(self.proj(x))           # (B, S, d_model)
        pe = self.pe(timestamps)              # (B, S, d_model)
        z = z + pe
        # CRITICAL: src_key_padding_mask — True means IGNORE that position
        padding_mask = ~mask  # (B, S); True for padding positions
        z = self.encoder(z, src_key_padding_mask=padding_mask)
        # Mean-pool over valid positions only
        valid_mask = mask.unsqueeze(-1).float()  # (B, S, 1)
        pooled = (z * valid_mask).sum(dim=1) / valid_mask.sum(dim=1).clamp(min=1)  # (B, d_model)
        if self.n_categories > 0 and category_onehot is not None:
            pooled = torch.cat([pooled, category_onehot.float()], dim=-1)
        return self.mlp(pooled)  # (B, 1)
