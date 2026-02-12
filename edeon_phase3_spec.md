# Edeon Phase 3 — Environmental Fate Tier-1 Model Implementation Specification

**Audience:** coding agent.
**Goal:** train Tier-1 reference models for the three Environmental Fate endpoints (Koc, DT50, GUS) and deploy them as the new backend for the fate gauge UI. Koc reuses the Phase 2 ensemble recipe. DT50 introduces a heteroscedastic probabilistic model that captures both compound-level uncertainty and the irreducible inter-soil variability documented by Gnann et al. 2025 (*Environ. Sci. Technol.*). GUS is a composite endpoint with no training of its own — it propagates the joint Koc/DT50 uncertainty through the Gustafson formula via Monte Carlo sampling.

**Inputs:** Phase 1 curated datasets at `data/curated/soil_koc/v1.0/` and `data/curated/soil_dt50/v1.0/`. Phase 2 shared infrastructure (`edeon_train/shared/*`) and Phase 0 architecture.

**Outputs:** trained model checkpoints at `data/checkpoints/{soil_koc,soil_dt50}/v1.0/`, a composite GUS backend, model cards, validation reports, and frontend updates to the fate gauge to display propagated uncertainty.

This phase is genuinely novel in the DT50 piece. The naive approach (RMSE-optimised point predictions) actively misrepresents the science — soil DT50 has irreducible experimental variability of 0.5–1 log unit even for the same compound. Treat this seriously.

---

## 0. Context and Hard Rules

**Hard rule 1: NLL is the primary loss for DT50, not MSE/RMSE.**
A model with low RMSE but miscalibrated intervals is a worse scientific artefact than a model with slightly higher RMSE and well-calibrated intervals. Phase 3 evaluates DT50 primarily by:
- Negative log-likelihood (NLL) on a held-out set (proper scoring rule)
- Empirical coverage of 95% credible interval
- Per-compound variance estimation: does predicted σ track observed within-compound spread?

RMSE is reported but secondary.

**Hard rule 2: DT50 preserves multi-record structure during training.**
Phase 1's curated DT50 dataset has multiple records per compound from different soil studies (EAWAG-SOIL). Do NOT aggregate to one row per compound before training. The model needs the within-compound spread to learn the aleatoric variance head. Aggregate only at the *evaluation* step, when comparing predicted vs. observed compound-level variance.

**Hard rule 3: test set protection (same as Phase 2).**
Use the Phase 2 `TestSetGate` mechanism. Test set evaluated exactly once per endpoint.

**Hard rule 4: GUS is composite, not trained.**
GUS = log10(DT50) × (4 − log10(Koc)) is a deterministic formula. The GUS backend wraps the Koc and DT50 backends and propagates their joint uncertainty via Monte Carlo. No GUS training data is required.

**Hard rule 5: ionizable compound flagging in Koc.**
Phase 1 already flagged ionizable compounds with `quality_flags=["ionizable"]`. The Koc model:
- Includes an `ionizable_flag` feature at training and inference time
- Reports performance separately for ionizable vs. non-ionizable subsets
- Documents the higher uncertainty for ionizables in the model card

---

## 1. Tech Stack Assumptions

In addition to Phase 2's stack:

- **PyTorch ≥ 2.0** with `torch.distributions` for probabilistic outputs
- **PyTorch Lightning ≥ 2.0** (or plain PyTorch loops; Lightning recommended for the heteroscedastic model)
- **Chemprop ≥ 2.0**: required for DT50 — Chemprop 2.x supports `MveLoss` (mean-variance estimation) and ensemble training natively
- **Optional**: PyMC ≥ 5 or NumPyro ≥ 0.13 for a Bayesian alternative DT50 model (off the critical path; document if used)
- **scipy.stats**: for Monte Carlo sampling in the GUS composite

The Bayesian PyMC/NumPyro approach is genuinely cleaner statistically but harder to implement reliably and slower to train. The default recommended approach is a heteroscedastic neural ensemble in PyTorch — simpler, faster, and matches the published Gnann et al. methodology in spirit if not exact form.

---

## 2. Architectural Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  edeon-train soil_koc all          (reuses Phase 2 pipeline)    │
│  edeon-train soil_dt50 all         (new heteroscedastic recipe) │
│  edeon-train gus_index deploy      (composite, no training)     │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
    ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │ Koc training     │ │ DT50 training    │ │ GUS composite    │
    │ (Phase 2 recipe) │ │ (Phase 3 recipe) │ │ (Phase 3 only)   │
    │                  │ │                  │ │                  │
    │ RF + XGB         │ │ Heteroscedastic  │ │ MC over          │
    │ + Chemprop ens.  │ │ NN + GNN ens.    │ │ Koc × DT50       │
    │ + Conformal CI   │ │ + Aleatoric σ²   │ │ joint dist.      │
    │ + Tanimoto AD    │ │ + Epistemic σ²   │ │                  │
    │                  │ │ + Tanimoto AD    │ │                  │
    └──────────────────┘ └──────────────────┘ └──────────────────┘
              │                  │                     │
              └──────────────────┼─────────────────────┘
                                 ▼
                  ┌──────────────────────────────┐
                  │  BackendRegistry             │
                  │  T1 fate models registered   │
                  │  GUSCompositeBackend         │
                  │   wraps Koc + DT50 backends  │
                  └──────────────────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │  Frontend: Fate Gauge        │
                  │  Koc:  X ± σ   [In domain]   │
                  │  DT50: Y days, 95% CI [a, b] │
                  │  GUS:  Z, 5–95% range [c, d] │
                  └──────────────────────────────┘
```

---

## 3. Repository Layout

```
edeon/
├── python/
│   ├── edeon_train/                          # Phase 2 package, extended
│   │   ├── shared/
│   │   │   ├── heteroscedastic.py            # NEW — mean-variance NN module
│   │   │   ├── nll_calibration.py            # NEW — NLL + coverage calibration
│   │   │   └── mc_propagation.py             # NEW — Monte Carlo composite predictions
│   │   ├── endpoints/
│   │   │   ├── soil_koc/                     # NEW
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   ├── train.py
│   │   │   │   └── card.py
│   │   │   ├── soil_dt50/                    # NEW
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   ├── train.py
│   │   │   │   └── card.py
│   │   │   └── gus_index/                    # NEW — composite, no training
│   │   │       ├── __init__.py
│   │   │       ├── config.yaml
│   │   │       └── card.py                   # Card composed from Koc + DT50
│   │   └── tests/
│   │       ├── test_heteroscedastic.py
│   │       └── test_mc_propagation.py
│   └── edeon_models/
│       └── backends/
│           └── trained/
│               ├── tier1_backend.py          # Existing (Phase 2)
│               ├── heteroscedastic_backend.py # NEW — DT50-style T1 backend
│               └── gus_composite_backend.py  # NEW — composite GUS
├── data/
│   └── checkpoints/
│       ├── soil_koc/v1.0/                    # Same structure as Phase 2 endpoints
│       ├── soil_dt50/v1.0/
│       │   ├── baselines/                    # MVE-trained baselines if any
│       │   ├── chemprop_mve/                 # 5-seed Chemprop with MveLoss
│       │   ├── ad_fingerprints.npz
│       │   ├── nll_calibration.npz           # NEW — calibration scalars for σ
│       │   ├── manifest.json
│       │   ├── model_card.yaml
│       │   └── validation_report.html
│       └── gus_index/v1.0/                   # Minimal — config + composite card
│           ├── composite_config.yaml         # Refs to Koc + DT50 checkpoints
│           └── model_card.yaml
├── docs/
│   ├── PHASE3_NOTES.md                       # NEW
│   ├── PHASE3_DT50_METHODOLOGY.md            # NEW — heteroscedastic protocol
│   └── TIER1_MODEL_CARDS/
│       ├── soil_koc.md
│       ├── soil_dt50.md
│       └── gus_index.md
└── .github/
    └── workflows/
        └── tier1_fate_regression.yml         # NEW — CI for fate models
```

---

## 4. Modeling Methodology Standards

### 4.1 Koc — reuse Phase 2 recipe with two additions

Apply the full Phase 2 ensemble recipe (RF + XGBoost + Chemprop ensemble + split conformal + Tanimoto AD).

**Phase 3 additions for Koc**:

1. **Ionizable flag as feature**: at featurization time, add a binary `ionizable_flag` derived from Phase 1's `quality_flags` field. Concatenate to baseline feature vector and pass as auxiliary input to Chemprop.
2. **Per-subset reporting**: validation report breaks down test set into `ionizable` and `non_ionizable` subsets, reporting RMSE/R²/coverage separately. This goes into the model card under `performance.subset_metrics`.

All other infrastructure (HPO, ensembling, conformal calibration, AD) is unchanged. The agent should be able to copy `endpoints/bee_acute_oral_ld50/` as a starting point and adapt.

**Performance targets** (aspirational, not gates):
- RMSE (log Koc) ≤ 0.5
- R² ≥ 0.75
- 95% CI empirical coverage in [0.93, 0.97]
- AD coverage of test set ≥ 60%

### 4.2 DT50 — heteroscedastic protocol

This is the new piece. The model predicts a Gaussian distribution per compound: mean μ and variance σ². The variance has two components:

- **Aleatoric variance σ²ₐ**: irreducible noise from inter-soil and inter-study variability for that compound. Learned per-prediction from the data.
- **Epistemic variance σ²ₑ**: model uncertainty about the true mean. Captured via the ensemble (variance across seeds).

Total predictive variance: σ²_total = σ²ₐ + σ²ₑ.

#### 4.2.1 Architecture

**Primary model**: Chemprop 2.x with `MveLoss` (mean-variance estimation). Chemprop's `MveLoss` outputs (μ, log σ²) per molecule and is trained with Gaussian negative log-likelihood:

NLL = 0.5 · (log σ² + (y − μ)² / σ²)

This is the same loss used by Kendall & Gal 2017 for heteroscedastic regression. Train 5 ensemble members with seeds [0, 1, 2, 3, 4].

**Baseline model** (for ensemble diversity): a heteroscedastic MLP on RDKit + Morgan features:

```python
# python/edeon_train/shared/heteroscedastic.py
import torch
import torch.nn as nn

class HeteroscedasticMLP(nn.Module):
    def __init__(self, feature_dim: int, hidden_dim: int = 512, depth: int = 3,
                 dropout: float = 0.1):
        super().__init__()
        layers = []
        in_dim = feature_dim
        for _ in range(depth):
            layers += [nn.Linear(in_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)]
            in_dim = hidden_dim
        self.shared = nn.Sequential(*layers)
        self.mean_head = nn.Linear(hidden_dim, 1)
        self.log_var_head = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.shared(x)
        mean = self.mean_head(h).squeeze(-1)
        log_var = self.log_var_head(h).squeeze(-1)
        # Clamp log_var for numerical stability
        log_var = torch.clamp(log_var, min=-10.0, max=10.0)
        return mean, log_var


def gaussian_nll_loss(mean: torch.Tensor, log_var: torch.Tensor, target: torch.Tensor,
                      var_min: float = 1e-6) -> torch.Tensor:
    var = torch.exp(log_var).clamp(min=var_min)
    return 0.5 * (log_var + (target - mean).pow(2) / var).mean()
```

Train 5 MLPs with the same seed pattern.

#### 4.2.2 Multi-record handling

Phase 1's DT50 curated dataset has *one row per measurement*, not per compound. Many compounds appear multiple times.

**During training**:
- Each row is one training example. Do not deduplicate.
- The model sees the same compound with different y values across rows; the variance head learns to model this spread.
- Scaffold-stratified k-fold CV must be done by *compound* not by row — all rows for one compound go into the same fold to prevent leakage.

```python
# Pseudocode for compound-level fold assignment
compounds = df["inchikey"].unique()
scaffold_per_compound = {c: get_scaffold(df[df["inchikey"]==c]["smiles_canonical"].iloc[0])
                          for c in compounds}
fold_per_compound = scaffold_split_groups(scaffold_per_compound, n_folds=5)
df["fold"] = df["inchikey"].map(fold_per_compound)
```

#### 4.2.3 Ensemble combination

For each query compound:
1. Each ensemble member k predicts (μₖ, σ²ₖ).
2. Combine via mixture of Gaussians:
   - Combined mean: μ = (1/K) Σ μₖ
   - Combined variance: σ² = (1/K) Σ (σ²ₖ + μ²ₖ) − μ² = σ²_epistemic + σ²_aleatoric_avg
3. Epistemic component: σ²ₑ = Var(μₖ) across seeds.
4. Aleatoric component: σ²ₐ = (1/K) Σ σ²ₖ.

Report both components separately in the prediction provenance.

#### 4.2.4 Calibration

The mixture-of-Gaussians intervals are usually slightly *miscalibrated* — overconfident in well-sampled regions, underconfident in sparse regions. Apply a post-hoc calibration scalar:

```python
class VarianceScaler:
    """Scales predicted σ² by a constant fit on a held-out calibration set."""

    def __init__(self):
        self.scale_: Optional[float] = None

    def calibrate(self, mu_cal: np.ndarray, sigma2_cal: np.ndarray,
                  y_cal: np.ndarray, target_coverage: float = 0.95) -> None:
        """Find the σ²-scale factor such that empirical coverage hits target."""
        from scipy.optimize import brentq
        from scipy.stats import norm

        def coverage_deficit(scale):
            sigma_scaled = np.sqrt(sigma2_cal * scale)
            z = norm.ppf(0.5 + target_coverage / 2)
            lo, hi = mu_cal - z * sigma_scaled, mu_cal + z * sigma_scaled
            return ((y_cal >= lo) & (y_cal <= hi)).mean() - target_coverage

        # Scale factor lives in [0.1, 100] for stability
        try:
            self.scale_ = brentq(coverage_deficit, 0.1, 100.0)
        except ValueError:
            # If even the unscaled is over/under coverage, fall back to 1.0
            self.scale_ = 1.0

    def apply(self, sigma2: np.ndarray) -> np.ndarray:
        return sigma2 * self.scale_
```

Save the scaler in `nll_calibration.npz`.

**Important**: scaling σ² affects calibration but NOT the point predictions. The mean μ is unchanged.

#### 4.2.5 Evaluation

Primary metrics for DT50:
- **NLL on test set** (lower is better; report in log10-DT50-days units)
- **95% credible interval empirical coverage** (target: 90–98%)
- **Mean interval width** (in log10 days; report median and 95th percentile)
- **Predicted-vs-observed σ correlation**: for compounds with ≥ 3 records, compute observed within-compound std; correlate with model's mean predicted σ. Spearman ρ ≥ 0.3 indicates the variance head is learning meaningful structure.

Secondary metrics:
- RMSE / MAE / R² (for comparison with published baselines)
- Per-chemical-class breakdown (organochlorines, neonics, azoles, etc.)
- AD coverage breakdown

**Performance targets**:
- NLL (log10 DT50) ≤ 1.5
- 95% CI coverage in [0.90, 0.98]
- Median CI width ≤ 1.0 log unit (factor of 10 in days)
- AD coverage of test set ≥ 50%

The NLL target reflects the irreducible 0.5–1 log unit experimental variability; do not expect lower.

### 4.3 GUS — composite Monte Carlo

GUS = log10(DT50_days) × (4 − log10(Koc_L_per_kg))

#### 4.3.1 Inputs

At inference, query both backends:
- Koc backend: returns (μ_K, σ_K) per compound (μ in log10 L/kg, σ symmetric from conformal CI)
- DT50 backend: returns (μ_D, σ_D) per compound (μ in log10 days, σ from mixture-of-Gaussians)

Both quantities are in log10 space already. Assume Gaussian residuals in log space (this is the standard assumption; document it).

#### 4.3.2 Propagation

Monte Carlo sampling:

```python
def gus_monte_carlo(mu_K: float, sigma_K: float, mu_D: float, sigma_D: float,
                    n_samples: int = 10_000, rng: np.random.Generator = None) -> dict:
    """Sample GUS distribution and return summary statistics.

    Assumes Koc and DT50 are independent (standard assumption — document).
    """
    rng = rng or np.random.default_rng(seed=42)
    K_samples = rng.normal(mu_K, sigma_K, size=n_samples)
    D_samples = rng.normal(mu_D, sigma_D, size=n_samples)
    gus_samples = D_samples * (4.0 - K_samples)
    return {
        "median": float(np.median(gus_samples)),
        "mean": float(np.mean(gus_samples)),
        "ci_lower": float(np.quantile(gus_samples, 0.025)),
        "ci_upper": float(np.quantile(gus_samples, 0.975)),
        "p05": float(np.quantile(gus_samples, 0.05)),
        "p95": float(np.quantile(gus_samples, 0.95)),
        "leaching_class_distribution": _classify(gus_samples),  # see below
    }


def _classify(gus_samples: np.ndarray) -> dict[str, float]:
    """Returns probability of falling in each Gustafson class."""
    return {
        "non_leacher": float((gus_samples < 1.8).mean()),
        "transition": float(((gus_samples >= 1.8) & (gus_samples <= 2.8)).mean()),
        "leacher": float((gus_samples > 2.8).mean()),
    }
```

**Note on independence**: Koc and DT50 are not strictly independent (lipophilic compounds tend to be both more sorbed and more persistent). The simplifying assumption is documented in the GUS model card under `known_failure_modes`.

If at any point a structured covariance becomes available (e.g., from a joint embedding), the composite can be updated to sample from a multivariate normal — but for v1.0, independent sampling is acceptable and explicit.

#### 4.3.3 AD for composite

GUS AD = min(Koc AD status, DT50 AD status), with the ordinal mapping IN < BORDERLINE < OUT < UNKNOWN. A compound is "out of GUS domain" if it's out of either component's domain. Report both component AD statuses in the prediction provenance.

#### 4.3.4 No training

The GUS backend has no training data and no checkpoints to ship. Its "version" is derived from the component versions: `gus-{koc.version}_{dt50.version}`. The model card is auto-generated at deployment time from the component cards.

---

## 5. Per-Endpoint Specifications

### 5.1 soil_koc

```yaml
# python/edeon_train/endpoints/soil_koc/config.yaml
endpoint: soil_koc
phase1_dataset: data/curated/soil_koc/v1.0
target_column: value_log
target_kind: regression
primary_split: scaffold
additional_splits: [random]
calibration_split: scaffold/cal
test_split: scaffold/test
baseline_models: [random_forest, xgboost]
include_chemprop: true
auxiliary_features: [ionizable_flag]
chemprop:
  hpo_trials: 20
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 50
ad:
  k: 5
  fp_radius: 2
  fp_bits: 2048
conformal:
  alpha: 0.05
  method: split
performance_targets:
  rmse_log: 0.5
  r2: 0.75
  coverage_95: 0.95
  ad_coverage_test: 0.6
subset_reporting: [ionizable, non_ionizable]
deployment:
  endpoint_id: soil_koc
  tier: 1
  fallback_to_tier: 2
```

### 5.2 soil_dt50

```yaml
# python/edeon_train/endpoints/soil_dt50/config.yaml
endpoint: soil_dt50
phase1_dataset: data/curated/soil_dt50/v1.0
target_column: value_log
target_kind: regression_heteroscedastic
primary_split: scaffold
additional_splits: [random]
calibration_split: scaffold/cal
test_split: scaffold/test
multi_record_per_compound: true
fold_grouping: inchikey
include_chemprop_mve: true
include_heteroscedastic_mlp: true
chemprop_mve:
  loss: mve  # Chemprop 2.x MveLoss
  hpo_trials: 20
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 80
  early_stopping_metric: val_nll
heteroscedastic_mlp:
  hidden_dim: 512
  depth: 3
  dropout: 0.1
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 200
  early_stopping_metric: val_nll
  optimizer: adam
  lr: 5e-4
calibration:
  method: variance_scaler  # post-hoc σ² scaling for coverage target
  target_coverage: 0.95
ad:
  k: 5
  fp_radius: 2
  fp_bits: 2048
performance_targets:
  nll_log10: 1.5
  coverage_95: [0.90, 0.98]
  median_ci_width_log10: 1.0
  ad_coverage_test: 0.5
  predicted_vs_observed_sigma_spearman: 0.3
deployment:
  endpoint_id: soil_dt50
  tier: 1
  fallback_to_tier: 2
```

### 5.3 gus_index

```yaml
# python/edeon_train/endpoints/gus_index/config.yaml
endpoint: gus_index
composite: true
component_endpoints:
  - soil_koc
  - soil_dt50
component_versions:
  soil_koc: ">=1.0,<2.0"
  soil_dt50: ">=1.0,<2.0"
monte_carlo:
  n_samples: 10000
  seed: 42
  assume_independence: true
classification_thresholds:
  non_leacher_max: 1.8
  leacher_min: 2.8
deployment:
  endpoint_id: gus_index
  tier: 1
  fallback_to_tier: 2  # The legacy GUS formula on T2 Koc + T2 DT50
```

---

## 6. Task Manifest

---

### Group A — Shared Infrastructure Extensions

#### Task A1: Heteroscedastic module
**Depends on:** Phase 2 complete.
**File:** `python/edeon_train/shared/heteroscedastic.py`
**Action:** Implement `HeteroscedasticMLP`, `gaussian_nll_loss`, training loop with early stopping on val NLL, ensemble training utility, ensemble prediction with mixture-of-Gaussians aggregation.

```python
def train_heteroscedastic_ensemble(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    config: dict, output_dir: Path,
    seeds: list[int] = [0, 1, 2, 3, 4],
) -> dict:
    """Trains K models with different seeds. Saves each as state_dict in
    output_dir/seed_{k}.pt. Returns per-seed val NLL."""


def predict_heteroscedastic_ensemble(
    X: np.ndarray, checkpoint_dir: Path
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Returns (mu_combined, var_combined, var_epistemic, var_aleatoric)."""
```

**Acceptance:** Unit test: on synthetic regression with known heteroscedastic noise (σ varies linearly with X), the trained ensemble recovers σ within 30% relative error in the data-dense region.

---

#### Task A2: NLL + coverage calibration utilities
**Depends on:** A1.
**File:** `python/edeon_train/shared/nll_calibration.py`

```python
class VarianceScaler:
    """Post-hoc σ² scaling for empirical coverage targeting."""
    ...

def empirical_coverage(mu, sigma, y_true, level: float = 0.95) -> float: ...
def nll_score(mu, sigma2, y_true) -> float: ...
def calibration_curve(mu, sigma, y_true, n_bins: int = 10) -> dict: ...
```

**Acceptance:** On synthetic data, `VarianceScaler` brings miscalibrated predictions to within 2 percentage points of target coverage.

---

#### Task A3: Monte Carlo propagation utility
**Depends on:** A1.
**File:** `python/edeon_train/shared/mc_propagation.py`
**Action:** Implement `gus_monte_carlo` per Section 4.3.2. Add a general utility `propagate_composite(mu_components, sigma_components, formula, n_samples)` that takes a callable formula and propagates uncertainty. GUS is the first user; later phases may add others (e.g., a freshwater PEC composite).

**Acceptance:** Round-trip test: take (μ_K=2.5, σ_K=0.3) and (μ_D=1.5, σ_D=0.4), verify the Monte Carlo GUS median is within 5% of the analytical expected value E[GUS] = μ_D × (4 − μ_K) plus the cross-term correction.

---

#### Task A4: Compound-level scaffold splitting
**Depends on:** Phase 2 infrastructure.
**File:** Extend `python/edeon_train/shared/baselines.py` or `splits.py` (depending on Phase 2 layout).
**Action:** Add `scaffold_split_by_group(df, group_col, ratios, seed)` that ensures all rows with the same `group_col` value land in the same fold. Needed for DT50's per-row training with per-compound CV.

**Acceptance:** Unit test verifies that no `inchikey` is split across folds.

---

### Group B — Soil Koc Training

#### Task B1: Endpoint config and orchestrator
**Depends on:** A1, Phase 2 done.
**Files:** `python/edeon_train/endpoints/soil_koc/{config.yaml, train.py}`
**Action:** Copy the Phase 2 bee_acute_oral_ld50 endpoint folder as a template. Modify:
- Config per Section 5.1.
- `train.py` adds the `ionizable_flag` to baseline features and to Chemprop's `--features-path` argument (or 2.x equivalent).
- Per-subset metrics computed in evaluation: split test set by ionizable flag and report separately.

**Acceptance:** `edeon-train soil_koc train` runs to completion. HPO histories saved.

---

#### Task B2: Run full Koc pipeline
**Depends on:** B1.
**Action:**
1. `edeon-train soil_koc train` — train baselines + Chemprop ensemble.
2. `edeon-train soil_koc calibrate` — fit split conformal on cal.
3. `edeon-train soil_koc evaluate` — test gate opens once. Generate validation_report.html with overall + ionizable + non-ionizable subset metrics.
4. `edeon-train soil_koc deploy` — wraps in TrainedTier1Backend (Phase 2's class), registers.

**Acceptance:** All checkpoints at `data/checkpoints/soil_koc/v1.0/`. Performance targets met OR documented gap.

---

#### Task B3: Model card
**Depends on:** B2.
**File:** `python/edeon_train/endpoints/soil_koc/card.py` + `docs/TIER1_MODEL_CARDS/soil_koc.md`.
**Action:** Generate per-Phase-2-pattern. Include subset_metrics for ionizable / non-ionizable. List `known_failure_modes`: pH-dependent sorption, soil type variability, ionizable compounds with extreme pKa.

**Acceptance:** Model card present in SQLite and as markdown.

---

### Group C — Soil DT50 Training

#### Task C1: Endpoint config and orchestrator skeleton
**Depends on:** A1, A2, A4.
**Files:** `python/edeon_train/endpoints/soil_dt50/{config.yaml, train.py}`
**Action:** Implement per Section 5.2. The training script must:

```python
# Pseudocode
def main():
    cfg = load_config()
    df = load_phase1_curated("soil_dt50/v1.0")  # multi-record-per-compound preserved
    train_df, cal_df = load_train_cal_only(df, split="scaffold")  # no test access

    # Compound-level grouping for CV
    compound_groups = train_df["inchikey"]
    scaffolds = extract_scaffolds_per_compound(train_df)
    cv_folds = scaffold_split_by_group(train_df, "inchikey", n_folds=5, scaffolds=scaffolds)

    # HPO for hMLP and Chemprop-MVE in parallel
    hmlp_best = hpo_heteroscedastic_mlp(train_df, cv_folds, n_trials=20)
    chemprop_mve_best = hpo_chemprop_mve(train_df, cv_folds, n_trials=20)

    # Train 5-seed ensembles
    train_hmlp_ensemble(train_df, hmlp_best, output_dir=ckpt/"hmlp", seeds=[0..4])
    train_chemprop_mve_ensemble(train_df, chemprop_mve_best, output_dir=ckpt/"chemprop_mve", seeds=[0..4])

    # Predict on cal set with both ensembles, combine
    mu_cal, sigma2_cal = predict_combined_dt50(cal_df, ckpt)

    # Variance scaler calibration
    scaler = VarianceScaler()
    scaler.calibrate(mu_cal, sigma2_cal, cal_df["value_log"].values, target_coverage=0.95)
    scaler.save(ckpt/"nll_calibration.npz")

    # AD on training set
    ad = TrainedTanimotoAD.from_training_smiles(train_df["smiles_canonical"].unique())
    ad.save(ckpt/"ad_fingerprints.npz")
```

Note: `predict_combined_dt50` averages the hMLP-ensemble and Chemprop-MVE-ensemble distributions. The simplest correct combination is to treat them as 10 ensemble members total and aggregate via mixture-of-Gaussians.

**Acceptance:** Training script runs to completion on a small (100-compound) subsample to verify plumbing before running the full dataset.

---

#### Task C2: Chemprop-MVE wrapper
**Depends on:** A1.
**File:** Extend `python/edeon_train/shared/chemprop_wrapper.py` with MVE-loss variant:

```python
def train_chemprop_mve_ensemble(
    train_smiles, train_y, cal_smiles, cal_y,
    config, output_dir, seeds=[0,1,2,3,4],
) -> dict:
    """Train 5 Chemprop models with MveLoss (mean-variance estimation)."""

def predict_chemprop_mve_ensemble(
    smiles, checkpoint_dir,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns per-seed (mu, sigma2) stacked, plus combined mixture stats."""
```

If using Chemprop 2.x: use `chemprop.models.MultiComponentMoleculeModel` with `MveLoss` regression head. If Chemprop 1.x: invoke via CLI with `--loss_function mve` and parse outputs.

**Acceptance:** Trains on bee oral subsample with MveLoss and produces (μ, σ²) pairs. Coverage on small held-out set is roughly correct (≥ 80%, < 100% if data is informative).

---

#### Task C3: DT50 evaluation
**Depends on:** C1, C2, A2.
**Action:** Evaluation script computes:
- NLL on test
- 95% CI empirical coverage on test
- Median and 95th-percentile CI width
- Predicted-vs-observed σ correlation (for compounds with ≥ 3 records, compute observed std of log10(DT50) across rows; correlate with mean predicted σ)
- Standard regression metrics (RMSE, R², Spearman) — secondary
- Per-class breakdown using `shared/compound_classes.py`
- AD coverage breakdown

**Acceptance:** Validation report generated. NLL within target.

---

#### Task C4: Run full DT50 pipeline
**Depends on:** C1, C2, C3.
**Action:** Full pipeline: train → calibrate → evaluate → generate card. Same flow as Koc but with NLL as primary metric. Test gate opens exactly once.

**Acceptance:** All artefacts present. Model card complete.

---

#### Task C5: DT50 methodology document
**Depends on:** C4.
**File:** `docs/PHASE3_DT50_METHODOLOGY.md`
**Action:** Document the full DT50 protocol:
- Why heteroscedastic (link to Gnann 2025 ES&T)
- Multi-record handling rationale
- Per-compound CV grouping
- MveLoss / NLL training
- Mixture-of-Gaussians ensemble combination
- Variance scaler calibration
- Evaluation philosophy (NLL > RMSE)
- Known failure modes

This document is publication-ready (intended audience: Paper 3 reviewers and external researchers reproducing the method).

**Acceptance:** Document is complete and internally consistent.

---

#### Task C6: HeteroscedasticT1Backend
**Depends on:** C4.
**File:** `python/edeon_models/backends/trained/heteroscedastic_backend.py`
**Action:** Subclass of `ModelBackend` for the DT50-style backends:

```python
class HeteroscedasticTier1Backend(ModelBackend):
    """T1 backend for endpoints that ship heteroscedastic predictions."""

    def __init__(self, endpoint: Endpoint, checkpoint_dir: Path): ...

    def predict(self, smiles, conditions=None) -> list[Prediction]:
        # 1. Featurize (RDKit+Morgan for hMLP, raw SMILES for Chemprop-MVE)
        # 2. Predict per ensemble member
        # 3. Combine via mixture-of-Gaussians
        # 4. Apply variance scaler
        # 5. Compute 95% CI: mu ± 1.96 * sqrt(sigma2)
        # 6. Apply AD scoring
        # 7. Construct Prediction with provenance including:
        #    - mu, sigma2_total, sigma2_epistemic, sigma2_aleatoric
        #    - component contributions
        #    - scaler applied
```

**Acceptance:** Predicts on 10 known compounds; outputs have valid CIs with non-zero sigma. Provenance includes both variance components.

---

#### Task C7: Register DT50 backend
**Depends on:** C6.
**Action:** Extend `build_default_registry()` to load `HeteroscedasticTier1Backend` for DT50 when `data/checkpoints/soil_dt50/v1.0/` exists. Persist card to SQLite.

**Acceptance:** `reg.get(Endpoint.SOIL_DT50).tier() == 1` after deploy.

---

### Group D — GUS Composite Backend

#### Task D1: GUSCompositeBackend
**Depends on:** Koc T1 backend (B2) AND DT50 T1 backend (C7) registered.
**File:** `python/edeon_models/backends/trained/gus_composite_backend.py`

```python
class GUSCompositeBackend(ModelBackend):
    """GUS Tier-1 backend. Wraps Koc + DT50 backends; no training."""

    def __init__(self, registry: BackendRegistry,
                 mc_samples: int = 10_000,
                 mc_seed: int = 42):
        self._reg = registry
        self._koc = registry.get(Endpoint.SOIL_KOC, preferred_tier=1)
        self._dt50 = registry.get(Endpoint.SOIL_DT50, preferred_tier=1)
        self._mc_samples = mc_samples
        self._rng = np.random.default_rng(mc_seed)

    def endpoint(self) -> Endpoint: return Endpoint.GUS_INDEX
    def tier(self) -> int: return 1
    def version(self) -> str: return f"gus-{self._koc.version()}_{self._dt50.version()}"

    def predict(self, smiles, conditions=None) -> list[Prediction]:
        koc_preds = self._koc.predict(smiles)
        dt50_preds = self._dt50.predict(smiles)
        gus_preds = []
        for k, d in zip(koc_preds, dt50_preds):
            # Extract mu and sigma from each prediction's CI
            mu_K, sigma_K = self._extract_mu_sigma(k)
            mu_D, sigma_D = self._extract_mu_sigma(d)
            stats = gus_monte_carlo(mu_K, sigma_K, mu_D, sigma_D,
                                     n_samples=self._mc_samples, rng=self._rng)
            ad_status = self._combine_ad(k.ad_status, d.ad_status)
            gus_preds.append(self._build_prediction(stats, ad_status, k, d, smiles))
        return gus_preds

    def applicability_domain(self, smiles): ...
    def metadata(self) -> ModelCard:
        """Compose from component cards. Document independence assumption
        in known_failure_modes."""
```

The `_extract_mu_sigma` helper: from a Prediction with `ci_lower` and `ci_upper` (assumed symmetric in log space for both Koc and DT50), recover `mu = value_log` and `sigma = (ci_upper - ci_lower) / (2 * 1.96)`. For asymmetric intervals, use the median and the wider half-width (conservative).

**Acceptance:** End-to-end: predict GUS for imidacloprid SMILES, get median + CI. Verify against manual formula application at the component medians.

---

#### Task D2: Register GUS
**Depends on:** D1, D2 of B and C.
**Action:** Extend registry initialisation to register `GUSCompositeBackend` when both `Endpoint.SOIL_KOC` and `Endpoint.SOIL_DT50` have T1 backends available. If only one or zero T1 backends are present, do not register the T1 GUS backend; the T2 GUS (the legacy formula on top of T2 Koc/DT50) remains.

**Acceptance:** GUS Tier-1 only available when both components are Tier-1.

---

#### Task D3: GUS model card
**Depends on:** D1.
**File:** `python/edeon_train/endpoints/gus_index/card.py` + `docs/TIER1_MODEL_CARDS/gus_index.md`.
**Action:** Auto-generate. Document:
- Composite nature (no training)
- Component versions referenced
- Monte Carlo parameters
- Independence assumption (explicit in `known_failure_modes`: "Koc and DT50 are treated as independent in MC propagation; in practice they are weakly correlated for lipophilic persistent compounds, leading to slight CI overestimation in those regions.")
- Classification thresholds (non-leacher / transition / leacher per Gustafson)

**Acceptance:** Card complete.

---

### Group E — Frontend Updates

#### Task E1: Fate gauge displays propagated uncertainty
**Depends on:** D1.
**Files:** Locate the existing fate gauge component in `src/components/`. Update to consume the new Prediction shape that includes CI and AD.

For each of Koc, DT50, GUS:
- Display point value with units (Koc: log L/kg; DT50: days; GUS: unitless)
- Display CI as "[lower – upper]" or "± half-width" (whichever fits the gauge UI)
- Display TierBadge from Phase 0 components
- Display ADWarning from Phase 0 components
- For GUS specifically: visual gauge band shaded by 5–95% percentile range (the existing animated gauge becomes a *fuzzy* gauge — the indicator position is the median, the shaded band is the CI)
- Tooltip on GUS: "Predicted leaching class: 78% transition, 19% leacher, 3% non-leacher" (from `leaching_class_distribution` field)

**Acceptance:** Fate panel shows all three with CIs visibly distinct from point estimates. GUS gauge shows uncertainty band.

---

#### Task E2: Fate panel info button
**Depends on:** E1.
**Action:** Add a small "info" icon next to each fate metric. Clicking opens a popover that shows:
- Brief description (e.g., "Koc — soil organic carbon partition coefficient")
- The model card link
- The component decomposition for GUS (Koc and DT50 component values + uncertainties)
- Reference values for orientation (e.g., "Koc 1–3 = mobile, 3–4 = moderate, > 4 = strongly sorbed")

**Acceptance:** Info buttons work for all three fate metrics.

---

### Group F — Validation and CI

#### Task F1: Fate regression CI
**Depends on:** B2, C4, D1.
**File:** `.github/workflows/tier1_fate_regression.yml`

```yaml
name: Tier-1 Fate Regression
on: [push, pull_request]
jobs:
  fate_smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - name: Restore checkpoints
        run: ./scripts/sync_checkpoints.sh pull
      - name: Run T1 fate smoke tests
        run: pytest tests/regression/test_t1_fate_smoke.py -v
```

Smoke tests verify:
- Koc T1 backend loads and predicts on 20 reference compounds within tolerance.
- DT50 T1 backend loads and predicts; coverage on stored test compounds in [0.85, 1.00].
- GUS composite backend loads and predicts; CIs are non-trivial (width > 0.1).

Reference compounds and tolerances in `tests/regression/tier1_fate_tolerance.yaml`.

**Acceptance:** CI passes on first commit and detects drift on intentional regression.

---

#### Task F2: End-to-end fate test
**Depends on:** All previous tasks.
**File:** `tests/integration/test_t1_fate_e2e.py`

```python
def test_fate_gauge_e2e():
    registry = build_default_registry()

    # Imidacloprid: well-characterised, expected GUS ~ 2.5–4 (mobile/leacher)
    smiles = "Cc1ccnc(Cn2cnc(c2[N+](=O)[O-])C)c1"  # Imidacloprid SMILES
    koc = registry.get(Endpoint.SOIL_KOC).predict([smiles])[0]
    dt50 = registry.get(Endpoint.SOIL_DT50).predict([smiles])[0]
    gus = registry.get(Endpoint.GUS_INDEX).predict([smiles])[0]

    # Sanity: tiers
    assert koc.tier == 1
    assert dt50.tier == 1
    assert gus.tier == 1

    # Sanity: CIs are non-trivial
    assert (koc.ci_upper - koc.ci_lower) > 0.1
    assert (dt50.ci_upper - dt50.ci_lower) > 0.2  # DT50 should have wider CI
    assert (gus.ci_upper - gus.ci_lower) > 0.3

    # Sanity: GUS value lies between component-derived bounds
    # (this is a loose check; the formula is multiplicative so exact bounds
    # are not straightforward)
    assert 0.0 < gus.value.numeric < 10.0
```

**Acceptance:** Test passes.

---

#### Task F3: Benchmark results document
**Depends on:** B2, C4.
**File:** `docs/PHASE3_BENCHMARK_RESULTS.md`
**Action:** Auto-generated table summarising fate endpoints:

| Endpoint | n_train | n_cal | n_test | Primary metric | Value | Coverage(95%) | AD coverage |
|---|---|---|---|---|---|---|---|
| soil_koc | ... | ... | ... | RMSE | ... | ... | ... |
| soil_dt50 | ... | ... | ... | NLL | ... | ... | ... |

Plus per-endpoint subsections with calibration plots, per-class breakdowns, and links to validation reports.

**Acceptance:** Document generated and reflects current trained models.

---

## 7. Acceptance Criteria for Phase 3 Complete

Phase 3 is complete when:

1. Shared infrastructure (Group A) implemented and tested.
2. Koc T1 backend trained and deployed; performance targets met or documented gap.
3. DT50 T1 backend trained with heteroscedastic protocol; deployed; NLL within target; coverage within [0.90, 0.98].
4. GUS composite backend deployed when both components are Tier-1; falls back to T2 GUS otherwise.
5. Model cards complete and persisted for all three.
6. Frontend fate gauge displays propagated uncertainty for GUS, CIs for Koc and DT50.
7. CI regression workflow passes.
8. `PHASE3_DT50_METHODOLOGY.md` and `PHASE3_BENCHMARK_RESULTS.md` are populated.
9. `PHASE3_NOTES.md` documents deviations, Chemprop version used, GPU availability, calibration scaling factors applied.

---

## 8. Out of Scope (for Phase 3)

Do **not** in Phase 3:

- Train models for ecotox endpoints (Phase 2).
- Train models for mammalian tox / sensitisation (Phase 4).
- Build BCF, photostability, or selectivity backends.
- Replace Phase 0 or Phase 2 infrastructure.
- Implement true Bayesian posteriors via MCMC unless the heteroscedastic ensemble + scaler approach fails calibration targets and the agent has explicit justification documented.
- Implement joint multivariate predictions of Koc and DT50 (the independence assumption is acceptable for v1.0).
- Modify Phase 1 datasets.

---

## 9. Risk and Mitigation

| Risk | Mitigation |
|---|---|
| Chemprop 2.x MveLoss not stable | Fall back to heteroscedastic MLP only; downweight or drop Chemprop-MVE from the ensemble. Document. |
| DT50 NLL much higher than target | Try Mondrian conformal-style stratified σ-scaling (split into prediction-magnitude bins). If that fails, accept the gap and report honestly. |
| σ-prediction-vs-observed correlation < 0.3 | Indicates the variance head isn't learning meaningful structure. Try: deeper variance head; longer training; or fall back to homoscedastic prediction with global σ. Document either way. |
| GUS CI is unrealistically wide | This is the *honest* answer if both Koc and DT50 have wide CIs. The legacy product showed false precision; Phase 3 shows real uncertainty. Communicate clearly in the info popover. |
| Test gate violated by accident during HPO | Hard gate (Phase 2 Task A2) blocks; CI verifies test_set_evaluated count is exactly 1; manual code review of Group C scripts. |
| Compound-level CV grouping accidentally splits same compound | `scaffold_split_by_group` enforces; unit test verifies no inchikey across folds. |
| EAWAG-SOIL access blocked at Phase 1 → DT50 dataset incomplete | Cannot fix in Phase 3; document and either rerun Phase 1 with manual export or skip DT50 (Phase 3 still ships Koc + degraded GUS based on T2 DT50). |
| Variance scaler over-corrects on cal but test still miscalibrated | Indicates calibration set isn't representative. Document and consider quantile-stratified Mondrian calibration. |

---

## 10. Conventions

- Random seeds: `42` for splits, `[0, 1, 2, 3, 4]` for ensembles, `42` for Monte Carlo (deterministic by default; configurable).
- Logging: `edeon_train.soil_koc`, `edeon_train.soil_dt50`, `edeon_train.gus_index`.
- Provenance fields for DT50 predictions: include `mu`, `sigma2_total`, `sigma2_epistemic`, `sigma2_aleatoric`, `variance_scale_factor_applied`.
- Provenance fields for GUS predictions: include component μ and σ, MC samples count, MC seed, independence assumption flag.

---

## 11. Handoff Notes

Phase 3 outputs feed:
- **Paper 3** — the DT50 heteroscedastic methodology becomes either a major section in Paper 3 or a separate methods paper. The `PHASE3_DT50_METHODOLOGY.md` is the seed of that contribution.
- **Phase 4** (mammalian tox + sensitisation) — applies the Phase 2 recipe to rat LD50, skin sensitisation, etc.
- **Commercial pitch** — the fate gauge becomes the most differentiated module in the product. "Other tools show GUS as a point estimate; Edeon shows the actual uncertainty range and the leaching-class probability distribution." This is a sales talking point on its own.

The DT50 methodology in particular is publishable independently. If it works well (coverage and σ-prediction targets met), consider drafting it as a short methods paper for *Environ. Sci. Technol.* or *J. Cheminform.* with the curated dataset release as supplementary.

---

## 12. Deviation Log

Maintain `docs/PHASE3_NOTES.md` recording:
- Chemprop version and MveLoss availability.
- GPU hours per endpoint training run.
- Variance scaler factors applied per endpoint.
- Cases where coverage didn't reach target and the resolution.
- Whether Bayesian PyMC/NumPyro alternative was attempted and outcome.
- σ-prediction-vs-observed correlation per endpoint.
- Final test-set evaluation timestamps.

---

**End of Phase 3 Specification.**
