# Weeks 4-6 Report: Model Training and Evaluation

## 1. Architecture Specifications Summary

| Architecture | Key Hyperparameters |
|---|---|
| Linear (Ridge) | CV folds: 5; alphas: 50 log-spaced in [1e-4, 1e4] |
| LSTM/GRU | hidden_dim=128, window=5, dropout=0.1, proj_dim=256, max_epochs=100, patience=15 |
| Transformer | d_model=256, nhead=4, num_layers=2, window=20, tau_max_days=30, warmup=200 |
| TCN | channels=256, num_blocks=3, kernel_size=3, window=10, max_epochs=80, patience=12 |

All sequence models trained with AdamW. Hyperparameter search: random configs (n=12 for LSTM/Transformer, n=10 for TCN), evaluated on validation split.

---

## 2. Dataset Statistics

Observation counts by split and category:

| Split | All | Sports | Politics | Geopolitics |
|---|---|---|---|---|
| Train (before 2025-01-01) | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| Val (2025-01-01 – 2025-07-01) | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| Test (from 2025-07-01) | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |

---

## 3. Linear Baseline Results

Shock vs. raw embedding R²_OOS with 95% bootstrap CI (n=1000):

| Category | Shock R²_OOS | Raw R²_OOS | Δ R² | p-value |
|---|---|---|---|---|
| All | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| Sports | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| Politics | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| Geopolitics | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |

Direction accuracy (shock embedding):

| Category | Direction Accuracy |
|---|---|
| All | [PLACEHOLDER] |
| Sports | [PLACEHOLDER] |
| Politics | [PLACEHOLDER] |
| Geopolitics | [PLACEHOLDER] |

---

## 4. Architecture Comparison Matrix

4×3 R²_OOS table (shock embedding; rows = architecture, columns = category):

| Architecture | Sports | Politics | Geopolitics |
|---|---|---|---|
| Linear | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| LSTM | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| TCN | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| Transformer | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |

95% bootstrap CIs and pairwise tests reported in `results/bootstrap_cis.parquet`.

---

## 5. H1 Test Result

**H1:** Shock embeddings improve R²_OOS over raw embeddings for the best architecture.

Result: [PLACEHOLDER — REJECT / FAIL TO REJECT]

Interpretation: [PLACEHOLDER — e.g., "Shock embeddings increased R²_OOS by X pp (95% CI [lo, hi]) for the Transformer on the full test set, supporting H1."]

---

## 6. H2 Test Result

**H2:** At least one sequence model achieves R²_OOS > linear baseline on sports markets.

Result: [PLACEHOLDER — REJECT / FAIL TO REJECT]

Bootstrap test (n=5000): p = [PLACEHOLDER]; Δ R²_OOS = [PLACEHOLDER].

Interpretation: [PLACEHOLDER]

---

## 7. H3 Test Result

**H3:** Quantitative news achieves higher R²_OOS than high-attention news.

Result: [PLACEHOLDER — REJECT / FAIL TO REJECT]

Quantitative R²_OOS = [PLACEHOLDER]; High-attention R²_OOS = [PLACEHOLDER]; Δ = [PLACEHOLDER].

---

## 8. H4 Test Result

**H4:** Geopolitics markets show lower predictability (R²_OOS) than sports markets.

Result: [PLACEHOLDER — REJECT / FAIL TO REJECT]

Sports R²_OOS = [PLACEHOLDER]; Geopolitics R²_OOS = [PLACEHOLDER]; Δ = [PLACEHOLDER].

---

## 9. Scope Adjustments and Open Issues for Weeks 7-9

- [PLACEHOLDER — list any architecture changes, data quality issues, or hypothesis reformulations]
- GPU training time estimates for Colab: LSTM ~[PLACEHOLDER] hrs, Transformer ~[PLACEHOLDER] hrs, TCN ~[PLACEHOLDER] hrs
- Any markets removed from test set due to data quality: [PLACEHOLDER]
- Planned week 7-9 work: ensemble methods, Brier score decomposition, camera-ready figures
