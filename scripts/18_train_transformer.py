"""Script 18: Train Transformer predictor.

Usage:
    uv run python scripts/18_train_transformer.py --category all --embedding shock
    uv run python scripts/18_train_transformer.py --category sports --embedding raw --resume

Reads:  data/analysis/shock_embeddings.parquet
        config/training.yaml
        models/hparam_search/transformer_{category}_results.json  (optional)
Writes: models/checkpoints/transformer_{category}_{embedding}_best.pt
        results/metrics_all.parquet  (upserted)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import torch
import yaml
from torch.utils.data import DataLoader

from src.evaluation.metrics import compute_r2_oos, compute_direction_accuracy
from src.models.transformer_model import TransformerPredictor
from src.training.dataset import ArticleSequenceDataset
from src.training.forward import batch_forward, select_device
from src.training.trainer import Trainer
from src.utils import get_logger

SHOCK_PATH = Path("data/analysis/shock_embeddings.parquet")
CHECKPOINTS_DIR = Path("models/checkpoints")
RESULTS_PATH = Path("results/metrics_all.parquet")
HPARAM_DIR = Path("models/hparam_search")

INPUT_DIM = 768

log = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train Transformer predictor.")
    p.add_argument("--category", choices=["sports", "politics", "geopolitics", "all"], default="all")
    p.add_argument("--embedding", choices=["shock", "raw"], default="shock")
    p.add_argument("--config-path", default="config/training.yaml")
    p.add_argument("--resume", action="store_true", help="Resume from existing checkpoint if present.")
    p.add_argument("--device", default="auto", help="Device: auto|cuda|mps|cpu")
    return p.parse_args()


def _load_config(path: str) -> dict:
    cfg_path = Path(path)
    if cfg_path.exists():
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _load_best_hparams(category: str) -> dict | None:
    results_path = HPARAM_DIR / f"transformer_{category}_results.json"
    if not results_path.exists():
        return None
    with open(results_path) as f:
        results = json.load(f)
    if not results:
        return None
    best = min(results, key=lambda r: r.get("best_val_mse", float("inf")))
    return best.get("config", {})


def _run_inference(
    model: torch.nn.Module, loader: DataLoader, device: torch.device, embedding: str
) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for batch in loader:
            y = batch["y_logit_6h"].to(device)
            preds = batch_forward(model, batch, device, embedding).squeeze(-1)
            all_preds.append(preds.cpu().numpy())
            all_targets.append(y.cpu().numpy())
    return np.concatenate(all_preds), np.concatenate(all_targets)


def main() -> None:
    args = _parse_args()
    cfg = _load_config(args.config_path)
    arch_cfg: dict = cfg.get("transformer", {})
    device = select_device(args.device)

    cat_filter: str | None = args.category if args.category != "all" else None
    emb_col = "shock_embedding" if args.embedding == "shock" else "raw_embedding"

    if not SHOCK_PATH.exists():
        print("shock_embeddings.parquet not found — run script 13 first.")
        return

    hparams = _load_best_hparams(args.category)
    if hparams is None:
        log.info("transformer_train", msg="No hparam search results found; using defaults.")
        hparams = {"K": 5, "num_layers": 2, "nhead": 4, "d_model": 256, "d_ff": 512, "dropout": 0.1}
    else:
        log.info("transformer_train", msg=f"Loaded hparams from search: {hparams}")

    K = int(hparams.get("K", arch_cfg.get("window_size", 20)))
    num_layers = int(hparams.get("num_layers", arch_cfg.get("num_layers", 2)))
    nhead = int(hparams.get("nhead", arch_cfg.get("nhead", 4)))
    d_model = int(hparams.get("d_model", arch_cfg.get("d_model", 256)))
    d_ff = int(hparams.get("d_ff", arch_cfg.get("dim_feedforward", 512)))
    dropout = float(hparams.get("dropout", arch_cfg.get("dropout", 0.1)))
    tau_max_days = float(arch_cfg.get("tau_max_days", 30.0))

    batch_size = int(arch_cfg.get("batch_size", 32))
    max_epochs = int(arch_cfg.get("max_epochs", 100))
    patience = int(arch_cfg.get("patience", 15))
    warmup_steps = int(arch_cfg.get("warmup_steps", 200))
    opt_cfg: dict = arch_cfg.get("optimizer", {})
    lr = float(opt_cfg.get("lr", 5e-5))
    weight_decay = float(opt_cfg.get("weight_decay", 1e-4))

    train_ds = ArticleSequenceDataset(
        parquet_path=str(SHOCK_PATH),
        split="train",
        K=K,
        tau_max_days=tau_max_days,
        embedding_col=emb_col,
        category_filter=cat_filter,
    )
    val_ds = ArticleSequenceDataset(
        parquet_path=str(SHOCK_PATH),
        split="val",
        K=K,
        tau_max_days=tau_max_days,
        embedding_col=emb_col,
        category_filter=cat_filter,
    )
    test_ds = ArticleSequenceDataset(
        parquet_path=str(SHOCK_PATH),
        split="test",
        K=K,
        tau_max_days=tau_max_days,
        embedding_col=emb_col,
        category_filter=cat_filter,
    )

    if len(train_ds) == 0:
        print(f"No training data for category={args.category}. Exiting.")
        return

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    model = TransformerPredictor(
        input_dim=INPUT_DIM,
        d_model=d_model,
        nhead=nhead,
        num_layers=num_layers,
        dim_feedforward=d_ff,
        dropout=dropout,
        tau_max_days=tau_max_days,
    )

    ckpt_name = f"transformer_{args.category}_{args.embedding}_best.pt"
    ckpt_path = CHECKPOINTS_DIR / ckpt_name
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.resume and ckpt_path.exists():
        ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=True)
        model.load_state_dict(ckpt["model_state_dict"])
        log.info("transformer_train", msg=f"Resumed from {ckpt_path}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)

    # Linear warmup per step, then constant.  Stepped per batch inside training loop
    # via a LambdaLR whose lambda is clamped at 1.0 after warmup_steps.
    total_train_steps = max_epochs * max(len(train_loader), 1)

    def lr_lambda(current_step: int) -> float:
        if current_step < warmup_steps:
            return float(current_step + 1) / float(max(warmup_steps, 1))
        return 1.0

    # We use a per-epoch scheduler for compatibility with the Trainer loop.
    # Warmup is approximated as linear over the first warmup_steps epochs / len(loader).
    warmup_epochs = max(1, warmup_steps // max(len(train_loader), 1))
    scheduler = torch.optim.lr_scheduler.LinearLR(
        optimizer, start_factor=0.1, end_factor=1.0, total_iters=warmup_epochs
    )

    meta = {
        "arch": "transformer",
        "category": args.category,
        "embedding": args.embedding,
        "K": K,
        "d_model": d_model,
        "nhead": nhead,
        "num_layers": num_layers,
        "d_ff": d_ff,
        "dropout": dropout,
        "tau_max_days": tau_max_days,
    }

    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        train_loader=train_loader,
        val_loader=val_loader,
        checkpoint_path=str(ckpt_path),
        patience=patience,
        max_epochs=max_epochs,
        device=str(device),
        clip_grad_norm=1.0,
        embedding=args.embedding,
        meta=meta,
    )
    outcome = trainer.train()
    print(f"Best val MSE: {outcome['best_val_mse']:.6f}  (epoch {outcome['best_epoch']})")

    best_ckpt = torch.load(str(ckpt_path), map_location=device, weights_only=True)
    model.load_state_dict(best_ckpt["model_state_dict"])
    model.to(device)

    test_pred, test_true = _run_inference(model, test_loader, device, args.embedding)
    test_r2 = compute_r2_oos(test_true, test_pred)
    test_dir_acc = compute_direction_accuracy(test_true, test_pred)
    print(f"Test R²_OOS:  {test_r2:.6f}")
    print(f"Test Dir Acc: {test_dir_acc:.4f}")

    row = {
        "arch": "transformer",
        "category": args.category,
        "embedding": args.embedding,
        "val_mse": outcome["best_val_mse"],
        "best_epoch": outcome["best_epoch"],
        "test_r2_oos": test_r2,
        "test_direction_accuracy": test_dir_acc,
        "checkpoint": str(ckpt_path),
    }
    new_df = pd.DataFrame([row])
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if RESULTS_PATH.exists():
        existing = pd.read_parquet(RESULTS_PATH)
        mask = ~(
            (existing["arch"] == "transformer")
            & (existing["category"] == args.category)
            & (existing["embedding"] == args.embedding)
        )
        existing = existing[mask]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_parquet(RESULTS_PATH, index=False)
    print(f"Results written: {RESULTS_PATH}")
    print(f"Checkpoint:      {ckpt_path}")


if __name__ == "__main__":
    main()
