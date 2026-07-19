"""LSTM/GRU predictor for news-shock sequence model (§2.2)."""
from __future__ import annotations
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

class LSTMPredictor(nn.Module):
    def __init__(
        self,
        input_dim: int,
        proj_dim: int = 256,
        hidden_dim: int = 128,
        dropout: float = 0.1,
        use_gru: bool = False,
        n_categories: int = 0,
    ):
        super().__init__()
        self.proj = nn.Sequential(nn.Linear(input_dim, proj_dim), nn.ReLU())
        RNN = nn.GRU if use_gru else nn.LSTM
        self.rnn = RNN(
            input_size=proj_dim,
            hidden_size=hidden_dim,
            num_layers=1,
            batch_first=True,
        )
        self._init_rnn_weights()
        self.dropout = nn.Dropout(dropout)
        head_in = hidden_dim + n_categories
        self.head = nn.Linear(head_in, 1)
        self.n_categories = n_categories

    def _init_rnn_weights(self):
        for name, p in self.rnn.named_parameters():
            if "weight_hh" in name:
                nn.init.orthogonal_(p)
            elif "weight_ih" in name:
                nn.init.xavier_uniform_(p)
            elif "bias" in name:
                nn.init.zeros_(p)

    def forward(
        self,
        x: torch.Tensor,          # (B, K+1, d)
        mask: torch.Tensor,        # (B, K+1) bool; True=valid
        lengths: torch.Tensor,     # (B,) int; number of valid positions
        category_onehot: torch.Tensor | None = None,  # (B, n_categories)
    ) -> torch.Tensor:
        B, S, _ = x.shape
        x_proj = self.proj(x)  # (B, S, proj_dim)
        # Clamp lengths to at least 1 to avoid pack_padded_sequence crash
        lengths_cpu = lengths.clamp(min=1).cpu()
        packed = pack_padded_sequence(x_proj, lengths_cpu, batch_first=True, enforce_sorted=False)
        out, hidden = self.rnn(packed)
        # h_last: last hidden state (take the hidden from h_n, not the padded output)
        if isinstance(hidden, tuple):
            h_last = hidden[0].squeeze(0)  # (B, H)
        else:
            h_last = hidden.squeeze(0)     # GRU: (B, H)
        h_last = self.dropout(h_last)
        if self.n_categories > 0 and category_onehot is not None:
            h_last = torch.cat([h_last, category_onehot.float()], dim=-1)
        return self.head(h_last)  # (B, 1)
