"""Script 20: Evaluate all trained model checkpoints on the test split.

Discovers all checkpoints in models/checkpoints/:
  - .pkl files  → linear models
  - .pt files   → neural models (arch from filename: lstm_/transformer_/tcn_)

Checkpoint metadata (saved by Trainer via the meta= arg) is used to recover
the K and embedding type used during training — so eval always matches training.

Reads:  data/analysis/shock_embeddings.parquet
        models/checkpoints/*.pkl  *.pt
Writes: results/metrics_all.parquet
        results/test_predictions.parquet  (per-row preds for bootstrap CIs + H3)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from src.evaluation.metrics import compute_r2_oos, compute_direction_accuracy
from src.models.linear import LinearModel
from src.models.lstm_model import LSTMPredictor
from src.models.tcn_model import TCNPredictor
from src.models.transformer_model import TransformerPredictor
from src.training.dataset import ArticleDataset, ArticleSequenceDataset
from src.training.forward import batch_forward, select_device
from src.utils import get_logger

SHOCK_PATH = Path("data/analysis/shock_embeddings.parquet")
CHECKPOINTS_DIR = Path("models/checkpoints")
RESULTS_PATH = Path("results/metrics_all.parquet")
PREDICTIONS_PATH = Path("results/test_predictions.parquet")

INPUT_DIM = 768
DEFAULT_K = 5
BATCH_SIZE = 64

log = get_logger(__name__)


def _parse_checkpoint_name(stem: str) -> dict | None:
    """Parse filename stem like lstm_sports_shock_best → {arch, category, embedding}.

    Returns None if the stem doesn't match expected format.
    """
    for arch in ("lstm", "transformer", "tcn", "linear"):
        if stem.startswith(arch + "_"):
            rest = stem[len(arch) + 1:]
            rest = rest.removesuffix("_best")
            for emb in ("shock", "raw"):
                if rest.endswith("_" + emb):
                    cat = rest[: -(len(emb) + 1)]
                    return {"arch": arch, "category": cat, "embedding": emb}
    return None


def _eval_linear(ckpt_path: Path, parsed: dict) -> tuple[dict | None, pd.DataFrame | None]:
    """Evaluate a linear checkpoint. Returns (metrics_row, predictions_df)."""
    try:
        model = LinearModel.load(str(ckpt_path))
    except Exception as exc:
        log.info("eval", ckpt=str(ckpt_path), error=str(exc))
        return None, None

    if not SHOCK_PATH.exists():
        return None, None

    df = pd.read_parquet(SHOCK_PATH)
    df = df[df["valid_6h"] == True].copy()  # noqa: E712
    emb_col = "shock_embedding" if parsed["embedding"] == "shock" else "raw_embedding"
    cat = parsed["category"]

    def _filter(sub: pd.DataFrame) -> pd.DataFrame:
        if cat == "sports":
            return sub[sub["category"].isin({"nfl", "nba"})].copy()
        elif cat in ("politics", "geopolitics"):
            return sub[sub["category"] == cat].copy()
        return sub.copy()

    test_df = _filter(df[df["split"] == "test"])
    if len(test_df) == 0:
        return None, None

    X_test = np.stack(test_df[emb_col].tolist()).astype(np.float64)
    y_test = test_df["y_logit_6h"].to_numpy(dtype=np.float64)
    y_pred = model.predict(X_test)

    metrics = {
        "arch": "linear",
        "category": cat,
        "embedding": parsed["embedding"],
        "test_r2_oos": compute_r2_oos(y_test, y_pred),
        "test_direction_accuracy": compute_direction_accuracy(y_test, y_pred),
        "checkpoint": str(ckpt_path),
    }

    preds_df = pd.DataFrame({
        "arch": "linear",
        "category": cat,
        "embedding": parsed["embedding"],
        "article_id": test_df["article_id"].astype(str).values,
        "parent_event_id": test_df["parent_event_id"].fillna("").astype(str).values,
        "news_type": test_df["news_type"].fillna("").astype(str).values,
        "directional_impact": test_df["directional_impact"].astype(int).values,
        "y_true": y_test,
        "y_pred": y_pred,
    })

    return metrics, preds_df


def _load_neural_model(arch: str, ckpt_path: Path) -> tuple[torch.nn.Module | None, dict]:
    """Load a neural model from checkpoint; return (model, ckpt_meta)."""
    ckpt = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    state = ckpt.get("model_state_dict", ckpt)
    ckpt_meta: dict = ckpt.get("config", {})

    if arch == "lstm":
        try:
            proj_w = state["proj.0.weight"]   # (proj_dim, input_dim)
            proj_dim = proj_w.shape[0]
            rnn_w = state["rnn.weight_hh_l0"]  # (4*hidden, hidden) for LSTM
            hidden_dim = rnn_w.shape[1]
            model: torch.nn.Module = LSTMPredictor(
                input_dim=INPUT_DIM, proj_dim=proj_dim, hidden_dim=hidden_dim
            )
        except Exception:
            model = LSTMPredictor(input_dim=INPUT_DIM, proj_dim=256, hidden_dim=128)
    elif arch == "transformer":
        try:
            proj_w = state["proj.weight"]  # (d_model, input_dim)
            d_model = proj_w.shape[0]
            model = TransformerPredictor(
                input_dim=INPUT_DIM, d_model=d_model, nhead=4, num_layers=2
            )
        except Exception:
            model = TransformerPredictor(input_dim=INPUT_DIM, d_model=256, nhead=4, num_layers=2)
    elif arch == "tcn":
        try:
            proj_w = state["proj.weight"]  # (channels, input_dim, 1)
            channels = proj_w.shape[0]
            num_blocks = sum(
                1 for k in state if k.startswith("blocks.") and k.endswith(".conv1.conv.weight")
            )
            model = TCNPredictor(
                input_dim=INPUT_DIM, channels=channels, num_blocks=max(num_blocks, 1)
            )
        except Exception:
            model = TCNPredictor(input_dim=INPUT_DIM, channels=256, num_blocks=3)
    else:
        return None, ckpt_meta

    model.load_state_dict(state, strict=False)
    model.eval()
    return model, ckpt_meta


def _eval_neural(
    ckpt_path: Path, parsed: dict, device: torch.device
) -> tuple[dict | None, pd.DataFrame | None]:
    """Evaluate a neural checkpoint. Returns (metrics_row, predictions_df)."""
    arch = parsed["arch"]
    cat = parsed["category"]
    cat_filter: str | None = cat if cat != "all" else None

    model, ckpt_meta = _load_neural_model(arch, ckpt_path)
    if model is None:
        return None, None

    model.to(device)

    # Recover K and embedding from checkpoint meta; fall back to filename / defaults
    embedding = ckpt_meta.get("embedding", parsed["embedding"])
    K = int(ckpt_meta.get("K", DEFAULT_K))
    emb_col = "shock_embedding" if embedding == "shock" else "raw_embedding"

    try:
        test_ds = ArticleSequenceDataset(
            parquet_path=str(SHOCK_PATH),
            split="test",
            K=K,
            embedding_col=emb_col,
            category_filter=cat_filter,
        )
    except Exception as exc:
        log.info("eval", ckpt=str(ckpt_path), error=str(exc))
        return None, None

    if len(test_ds) == 0:
        return None, None

    loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False)
    all_preds, all_targets = [], []
    all_article_ids, all_event_ids = [], []
    all_news_types, all_dir_impacts = [], []

    with torch.no_grad():
        for batch in loader:
            y = batch["y_logit_6h"]
            preds = batch_forward(model, batch, device, embedding).squeeze(-1)
            all_preds.append(preds.cpu().numpy())
            all_targets.append(y.numpy())
            all_article_ids.extend(batch["article_id"])
            all_event_ids.extend(batch["parent_event_id"])
            all_news_types.extend(batch["news_type"])
            all_dir_impacts.extend(batch["directional_impact"].tolist())

    if not all_preds:
        return None, None

    y_pred = np.concatenate(all_preds)
    y_true = np.concatenate(all_targets)

    metrics = {
        "arch": arch,
        "category": cat,
        "embedding": embedding,
        "test_r2_oos": compute_r2_oos(y_true, y_pred),
        "test_direction_accuracy": compute_direction_accuracy(y_true, y_pred),
        "checkpoint": str(ckpt_path),
    }

    preds_df = pd.DataFrame({
        "arch": arch,
        "category": cat,
        "embedding": embedding,
        "article_id": all_article_ids,
        "parent_event_id": all_event_ids,
        "news_type": all_news_types,
        "directional_impact": all_dir_impacts,
        "y_true": y_true,
        "y_pred": y_pred,
    })

    return metrics, preds_df


def main() -> None:
    if not SHOCK_PATH.exists():
        print("shock_embeddings.parquet not found — run script 13 first.")
        return

    if not CHECKPOINTS_DIR.exists():
        print(f"No checkpoints directory found at {CHECKPOINTS_DIR}.")
        return

    device = select_device()
    print(f"Evaluating on device: {device}")

    pkl_files = list(CHECKPOINTS_DIR.glob("*.pkl"))
    pt_files = list(CHECKPOINTS_DIR.glob("*.pt"))
    print(f"Found {len(pkl_files)} linear checkpoints, {len(pt_files)} neural checkpoints.")

    results: list[dict] = []
    all_preds_dfs: list[pd.DataFrame] = []

    for ckpt_path in sorted(pkl_files):
        parsed = _parse_checkpoint_name(ckpt_path.stem)
        if parsed is None:
            print(f"Skipping unrecognised checkpoint: {ckpt_path.name}")
            continue
        print(f"Evaluating linear: {ckpt_path.name}")
        row, preds_df = _eval_linear(ckpt_path, parsed)
        if row:
            results.append(row)
            print(f"  R²_OOS={row['test_r2_oos']:.4f}  DirAcc={row['test_direction_accuracy']:.4f}")
        if preds_df is not None:
            all_preds_dfs.append(preds_df)

    for ckpt_path in sorted(pt_files):
        parsed = _parse_checkpoint_name(ckpt_path.stem)
        if parsed is None:
            print(f"Skipping unrecognised checkpoint: {ckpt_path.name}")
            continue
        print(f"Evaluating {parsed['arch']}: {ckpt_path.name}")
        row, preds_df = _eval_neural(ckpt_path, parsed, device)
        if row:
            results.append(row)
            print(f"  R²_OOS={row['test_r2_oos']:.4f}  DirAcc={row['test_direction_accuracy']:.4f}")
        if preds_df is not None:
            all_preds_dfs.append(preds_df)

    if not results:
        print("No results collected.")
        return

    results_df = pd.DataFrame(results)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_parquet(RESULTS_PATH, index=False)
    print(f"\nResults written: {RESULTS_PATH}")

    if all_preds_dfs:
        preds_combined = pd.concat(all_preds_dfs, ignore_index=True)
        preds_combined.to_parquet(PREDICTIONS_PATH, index=False)
        print(f"Per-row predictions written: {PREDICTIONS_PATH}")
        print(f"  ({len(preds_combined)} rows across {preds_combined['arch'].nunique()} architectures)")

    print("\n=== Summary ===")
    summary_cols = ["arch", "category", "embedding", "test_r2_oos", "test_direction_accuracy"]
    available = [c for c in summary_cols if c in results_df.columns]
    print(results_df[available].to_string(index=False))


if __name__ == "__main__":
    main()
