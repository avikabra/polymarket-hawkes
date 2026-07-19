"""Regression tests for src/training/hparam_search.py.

Covers:
  - _build_model constructs each arch without error (including the TCN num_channels bug fix)
  - _sample_configs respects the Transformer d_model % nhead constraint
  - random_hparam_search runs end-to-end on tiny synthetic data (smoke test)

Note: _build_model and random_hparam_search tests create real PyTorch models.
LSTMPredictor.__init__ calls torch.nn.init.orthogonal_ which segfaults on
Intel Mac + torch 2.2.x.  Those tests are skipped on Darwin and expected to
pass on Colab (Linux/CUDA).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from src.training.hparam_search import _build_model, _sample_configs, random_hparam_search

_IS_DARWIN = sys.platform == "darwin"
_SKIP_NEURAL = pytest.mark.skipif(
    _IS_DARWIN,
    reason="torch.nn.init.orthogonal_ segfaults on Intel Mac + torch 2.2.x; run on Colab",
)

# Tiny dim matching what synthetic parquet will use
_INPUT_DIM = 16
_D = 16   # embedding dim for synthetic data


# ── _build_model ──────────────────────────────────────────────────────────────

@_SKIP_NEURAL
def test_build_lstm():
    cfg = {"proj_dim": 16, "hidden_dim": 16, "dropout": 0.1}
    model = _build_model.__wrapped__(cfg) if hasattr(_build_model, "__wrapped__") else None
    # Call directly via module import
    from src.training.hparam_search import _build_model as bm
    import src.training.hparam_search as hs
    # Temporarily patch _INPUT_DIM
    original = hs._INPUT_DIM
    hs._INPUT_DIM = _INPUT_DIM
    try:
        model = bm("lstm", cfg)
        assert model is not None
        x = torch.randn(2, 4, _INPUT_DIM)
        mask = torch.ones(2, 4, dtype=torch.bool)
        lengths = torch.tensor([4, 4])
        out = model(x, mask, lengths)
        assert out.shape == (2, 1)
    finally:
        hs._INPUT_DIM = original


@_SKIP_NEURAL
def test_build_transformer():
    cfg = {"d_model": 16, "nhead": 2, "num_layers": 1, "d_ff": 32, "dropout": 0.1}
    import src.training.hparam_search as hs
    original = hs._INPUT_DIM
    hs._INPUT_DIM = _INPUT_DIM
    try:
        model = hs._build_model("transformer", cfg)
        x = torch.randn(2, 4, _INPUT_DIM)
        mask = torch.ones(2, 4, dtype=torch.bool)
        ts = torch.zeros(2, 4)
        out = model(x, ts, mask)
        assert out.shape == (2, 1)
    finally:
        hs._INPUT_DIM = original


@_SKIP_NEURAL
def test_build_tcn_channels_kwarg():
    """Regression test: TCNPredictor must receive channels= (not num_channels=)."""
    cfg = {"channels": 16, "num_blocks": 2, "dropout": 0.1}
    import src.training.hparam_search as hs
    original = hs._INPUT_DIM
    hs._INPUT_DIM = _INPUT_DIM
    try:
        model = hs._build_model("tcn", cfg)  # must NOT raise TypeError
        x = torch.randn(2, 4, _INPUT_DIM)
        mask = torch.ones(2, 4, dtype=torch.bool)
        out = model(x, mask)
        assert out.shape == (2, 1)
    finally:
        hs._INPUT_DIM = original


def test_build_unknown_arch_raises():
    import src.training.hparam_search as hs
    with pytest.raises(ValueError, match="Unknown arch"):
        hs._build_model("gpt4", {})


# ── _sample_configs ───────────────────────────────────────────────────────────

def test_sample_configs_transformer_constraint():
    """All sampled Transformer configs must have d_model % nhead == 0."""
    rng = np.random.default_rng(0)
    configs = _sample_configs("transformer", n_configs=20, rng=rng)
    for cfg in configs:
        assert cfg["d_model"] % cfg["nhead"] == 0, (
            f"d_model={cfg['d_model']} not divisible by nhead={cfg['nhead']}"
        )


def test_sample_configs_count():
    rng = np.random.default_rng(1)
    configs = _sample_configs("lstm", n_configs=5, rng=rng)
    assert len(configs) == 5


# ── random_hparam_search smoke test ──────────────────────────────────────────

def _make_tiny_parquet(path: Path, d: int = _INPUT_DIM, n: int = 60) -> None:
    """Write a minimal shock_embeddings.parquet for smoke testing."""
    rng = np.random.default_rng(42)
    rows = []
    cats = ["nfl"] * (n // 2) + ["politics"] * (n // 2)
    splits = (["train"] * (n // 3) + ["val"] * (n // 3) + ["test"] * (n // 3))
    splits = (splits + splits)[:n]  # ensure exactly n rows
    for i in range(n):
        ts = 1_700_000_000 + i * 3600
        rows.append({
            "article_id": f"a{i}",
            "market_id": f"m{i % 5}",
            "category": cats[i % len(cats)],
            "split": splits[i],
            "canonical_ts": ts,
            "valid_6h": True,
            "y_logit_6h": float(rng.standard_normal()),
            "y_logit_1h": float(rng.standard_normal()),
            "y_logit_24h": float(rng.standard_normal()),
            "valid_1h": True,
            "valid_24h": True,
            "shock_embedding": rng.standard_normal(d).astype(np.float32).tolist(),
            "raw_embedding": rng.standard_normal(d).astype(np.float32).tolist(),
            "news_type": "quantitative",
            "directional_impact": 1,
            "parent_event_id": f"ev{i % 3}",
        })
    pd.DataFrame(rows).to_parquet(path, index=False)


@_SKIP_NEURAL
def test_hparam_search_lstm_smoke():
    import src.training.hparam_search as hs
    original = hs._INPUT_DIM
    hs._INPUT_DIM = _INPUT_DIM
    try:
        with tempfile.TemporaryDirectory() as tmp:
            parquet = Path(tmp) / "shock_embeddings.parquet"
            _make_tiny_parquet(parquet, d=_INPUT_DIM, n=60)
            results = random_hparam_search(
                arch="lstm",
                category="all",
                parquet_path=str(parquet),
                config={},
                n_configs=2,
                max_epochs=2,
                device="cpu",
                seed=0,
            )
            assert len(results) > 0
            assert "best_val_mse" in results[0]
            assert np.isfinite(results[0]["best_val_mse"])
    finally:
        hs._INPUT_DIM = original


@_SKIP_NEURAL
def test_hparam_search_tcn_smoke():
    """TCN hparam search must not crash (regression test for num_channels bug)."""
    import src.training.hparam_search as hs
    original = hs._INPUT_DIM
    hs._INPUT_DIM = _INPUT_DIM
    try:
        with tempfile.TemporaryDirectory() as tmp:
            parquet = Path(tmp) / "shock_embeddings.parquet"
            _make_tiny_parquet(parquet, d=_INPUT_DIM, n=60)
            results = random_hparam_search(
                arch="tcn",
                category="all",
                parquet_path=str(parquet),
                config={},
                n_configs=2,
                max_epochs=2,
                device="cpu",
                seed=0,
            )
            assert len(results) > 0
    finally:
        hs._INPUT_DIM = original
