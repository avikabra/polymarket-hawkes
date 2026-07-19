"""Seeded random hyperparameter search for LSTM / Transformer / TCN models."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from src.training.dataset import ArticleSequenceDataset
from src.training.forward import select_device
from src.training.trainer import Trainer

# ---------------------------------------------------------------------------
# Per-architecture search grids
# ---------------------------------------------------------------------------

_GRIDS: dict[str, dict[str, list]] = {
    "lstm": {
        "hidden_dim": [64, 128, 256],
        "K": [3, 5, 10],
        "dropout": [0.1, 0.3],
        "proj_dim": [128, 256],
    },
    "transformer": {
        "num_layers": [1, 2, 3],
        "nhead": [2, 4],
        "d_model": [128, 256],
        "d_ff": [256, 512],
        "K": [5, 10, 20],
        "dropout": [0.1, 0.2],
    },
    "tcn": {
        "channels": [128, 256],
        "num_blocks": [2, 3, 4],
        "K": [5, 10, 15],
        "dropout": [0.1, 0.2],
    },
}

_INPUT_DIM = 768  # shock/raw embedding dimension (E5-large)


def _build_model(arch: str, cfg: dict) -> torch.nn.Module:
    """Instantiate a model from src.models.* given the arch and config dict."""
    if arch == "lstm":
        from src.models.lstm_model import LSTMPredictor
        return LSTMPredictor(
            input_dim=_INPUT_DIM,
            proj_dim=cfg["proj_dim"],
            hidden_dim=cfg["hidden_dim"],
            dropout=cfg["dropout"],
        )
    elif arch == "transformer":
        from src.models.transformer_model import TransformerPredictor
        return TransformerPredictor(
            input_dim=_INPUT_DIM,
            d_model=cfg["d_model"],
            nhead=cfg["nhead"],
            num_layers=cfg["num_layers"],
            dim_feedforward=cfg["d_ff"],
            dropout=cfg["dropout"],
        )
    elif arch == "tcn":
        from src.models.tcn_model import TCNPredictor
        return TCNPredictor(
            input_dim=_INPUT_DIM,
            channels=cfg["channels"],
            num_blocks=cfg["num_blocks"],
            dropout=cfg["dropout"],
        )
    else:
        raise ValueError(f"Unknown arch: {arch!r}")


def _sample_configs(arch: str, n_configs: int, rng: np.random.Generator) -> list[dict]:
    """Draw n_configs random configs from the arch grid, applying constraints."""
    grid = _GRIDS[arch]
    configs: list[dict] = []
    max_attempts = n_configs * 100

    for _ in range(max_attempts):
        if len(configs) >= n_configs:
            break
        cfg = {k: rng.choice(v).item() for k, v in grid.items()}
        # Transformer constraint: d_model must be divisible by nhead
        if arch == "transformer" and cfg["d_model"] % cfg["nhead"] != 0:
            continue
        configs.append(cfg)

    return configs


def random_hparam_search(
    arch: str,
    category: str,
    parquet_path: str,
    config: dict,
    n_configs: int,
    max_epochs: int = 30,
    device: str = "auto",
    embedding: str = "shock",
    output_path: str | None = None,
    seed: int = 42,
) -> list[dict]:
    """Run seeded random search. Returns top-3 configs sorted by best val MSE.

    Args:
        arch: "lstm" | "transformer" | "tcn"
        category: "sports" | "politics" | "geopolitics" | "all"
        parquet_path: path to shock_embeddings.parquet
        config: dict loaded from training.yaml (not used here but kept for
                forward compatibility with LR / batch_size fields)
        n_configs: number of random configurations to try
        max_epochs: cap on trainer epochs per config
        device: torch device string
        output_path: if provided, write JSON results here
        seed: random seed for reproducibility

    Returns:
        Top-3 result dicts sorted by ascending best_val_mse.
        Each dict has keys: arch, category, config, best_val_mse, best_epoch.
    """
    rng = np.random.default_rng(seed)
    resolved_device = str(select_device(device))
    cat_filter: str | None = category if category != "all" else None
    configs = _sample_configs(arch, n_configs, rng)

    results: list[dict] = []

    for i, cfg in enumerate(configs):
        K = int(cfg.get("K", 5))

        train_ds = ArticleSequenceDataset(
            parquet_path=parquet_path,
            split="train",
            K=K,
            tau_max_days=30.0,
            embedding_col="shock_embedding",
            category_filter=cat_filter,
        )
        val_ds = ArticleSequenceDataset(
            parquet_path=parquet_path,
            split="val",
            K=K,
            tau_max_days=30.0,
            embedding_col="shock_embedding",
            category_filter=cat_filter,
        )

        if len(train_ds) == 0 or len(val_ds) == 0:
            print(f"[hparam {i+1}/{len(configs)}] skipped — empty split for {category}")
            continue

        batch_size = int(config.get("batch_size", 32))
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

        model = _build_model(arch, cfg)
        lr = float(config.get("lr", 1e-3))
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)

        ckpt_path = f"/tmp/hparam_{arch}_{category}_{i}.pt"
        trainer = Trainer(
            model=model,
            optimizer=optimizer,
            scheduler=None,
            train_loader=train_loader,
            val_loader=val_loader,
            checkpoint_path=ckpt_path,
            patience=5,
            max_epochs=max_epochs,
            device=resolved_device,
            clip_grad_norm=1.0,
            embedding=embedding,
            meta={"arch": arch, "category": category, "embedding": embedding, **cfg},
        )
        outcome = trainer.train()

        result = {
            "arch": arch,
            "category": category,
            "config": cfg,
            "best_val_mse": outcome["best_val_mse"],
            "best_epoch": outcome["best_epoch"],
        }
        results.append(result)
        print(
            f"[hparam {i+1}/{len(configs)}] arch={arch} cfg={cfg} "
            f"val_mse={outcome['best_val_mse']:.6f}"
        )

    results.sort(key=lambda r: r["best_val_mse"])
    top3 = results[:3]

    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as fh:
            json.dump(results, fh, indent=2)
        print(f"Results written to {output_path}")

    return top3
