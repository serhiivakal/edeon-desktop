# Edeon Phase 2 — Tier-1 Ecotox Model Implementation Specification

**Audience:** coding agent.
**Goal:** for each of 6 ecotox endpoints (bee oral, bee contact, fish, Daphnia, algae, earthworm, bird), train a Tier-1 reference model consisting of an XGBoost/Random Forest baseline ensemble plus a Chemprop D-MPNN ensemble, calibrate prediction intervals via split conformal prediction, define an applicability domain via Tanimoto k-NN, generate a model card, and deploy the result as a Tier-1 backend in the registry — replacing the Tier-2 LogP-based defaults in the honeycomb. Also build an experimental-value overlay that surfaces measured values alongside predictions where curated Phase 1 data exists.

**Inputs:** Phase 1 curated datasets at `data/curated/<endpoint>/v1.0/`.
**Outputs:** trained model checkpoints at `data/checkpoints/<endpoint>/v1.0/`, T1 backend implementations registered at app startup, model cards in SQLite, validation reports.

This phase trains models. It does not curate data (Phase 1) or change UI components (mostly Phase 0; minor UI changes for experimental overlay specified here).

---

## 0. Context and Hard Rules

**Hard rule 1: the test set is touched exactly once per endpoint, at the very end.**
- All hyperparameter optimisation uses `splits/scaffold/train.parquet` with internal scaffold-split k-fold CV.
- Calibration uses `splits/scaffold/cal.parquet` (and matching time/random cal sets).
- The test set is evaluated *once* per endpoint after all model selection, calibration, and deployment decisions are frozen.
- Implement this gate in code: a single boolean `_test_set_evaluated` flag per endpoint, raise an exception if any test partition is loaded outside the final evaluation function.

**Hard rule 2: scaffold split is the headline reporting metric.**
Random split is reported for reference. Time split is reported where Phase 1 produced one. The scaffold split numbers are the ones that go into the model card's primary performance section.

**Hard rule 3: every deployed model carries calibrated CIs and a non-trivial AD.**
A Tier-1 backend with `ADStatus.UNKNOWN` is not Tier-1 — it's a Tier-2 that has been mislabelled. The deployment task includes verifying both before registering.

**Hard rule 4: no Phase 1 changes.**
The `data/curated/` tree is read-only from Phase 2's perspective. If a curation issue is discovered, document in `docs/PHASE2_NOTES.md` and skip the offending records — do not modify the curated dataset.

---

## 1. Tech Stack Assumptions

- **Python**: 3.11+
- **Core ML**: scikit-learn ≥ 1.4, xgboost ≥ 2.0, lightgbm (optional ensemble member)
- **Graph neural networks**: chemprop ≥ 2.0 (the rewritten version uses PyTorch Lightning; previous versions are acceptable if the agent documents the choice)
- **Hyperparameter optimisation**: optuna ≥ 3.5
- **Conformal prediction**: implement directly (split conformal is ~30 lines); optionally use mapie ≥ 0.8 or crepes for cross-validation
- **Chemistry**: RDKit (rdkit-pypi 2024.03.5+)
- **Tracking** (optional): mlflow or weights-and-biases; if not available, log to JSON files
- **Hardware**: GPU strongly recommended for Chemprop. CPU fallback works for small endpoints (bird, algae, earthworm) but will be slow. Document GPU availability in `docs/PHASE2_NOTES.md`.
- **IO**: Phase 1's Parquet artefacts; pickle for sklearn models; PyTorch checkpoints for Chemprop

The Phase 0 `ModelBackend` interface, Phase 1 `CuratedRecord` schema, and Phase 1 data card schema are *contracts*. Do not modify them. If a contract appears insufficient, document and propose in `PHASE2_NOTES.md`.

---

## 2. Architectural Overview

```
┌────────────────────────────────────────────────────────────────────┐
│             edeon-train CLI (one entry point per endpoint)         │
│  edeon-train <endpoint> hpo | train | calibrate | deploy | all     │
└────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
     ┌────────────────┐ ┌──────────────┐ ┌────────────────┐
     │ Shared training│ │ Per-endpoint │ │ Phase 0/1      │
     │ infrastructure │ │ orchestrators│ │ artefacts      │
     │                │ │              │ │ (read-only)    │
     │ featurize      │ │ bee_oral/    │ │                │
     │ baselines      │ │ bee_contact/ │ │ ModelBackend   │
     │ chemprop       │ │ fish/        │ │ Endpoint enum  │
     │ conformal      │ │ daphnia/     │ │ ModelCard      │
     │ ad             │ │ algae/       │ │ curated/*/v1.0 │
     │ ensemble       │ │ earthworm/   │ │                │
     │ evaluate       │ │ bird/        │ │                │
     └────────────────┘ └──────────────┘ └────────────────┘
                              │
                              ▼
                  ┌─────────────────────────┐
                  │   T1 backend factories  │
                  │  data/checkpoints/      │
                  │    <endpoint>/v1.0/     │
                  │      baselines/         │
                  │      chemprop/          │
                  │      calibration.npz    │
                  │      ad_fingerprints.npz│
                  │      model_card.yaml    │
                  └─────────────────────────┘
                              │
                              ▼
                  ┌─────────────────────────┐
                  │ BackendRegistry (Phase 0)│
                  │ T1 takes precedence over │
                  │ T2 legacy backends       │
                  └─────────────────────────┘
                              │
                              ▼
                  ┌─────────────────────────┐
                  │ Experimental Overlay     │
                  │ InChIKey → measured value│
                  │ Surfaces in Prediction   │
                  │   provenance             │
                  └─────────────────────────┘
```

---

## 3. Repository Layout

```
edeon/
├── python/
│   ├── edeon_train/                          # NEW
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   ├── config.py                          # Shared training config
│   │   ├── gates.py                           # Test-set protection gate
│   │   ├── shared/
│   │   │   ├── __init__.py
│   │   │   ├── featurize.py                   # RDKit + Morgan, MACCS, Avalon
│   │   │   ├── baselines.py                   # RF + XGBoost with Optuna HPO
│   │   │   ├── chemprop_wrapper.py            # Train/predict Chemprop ensembles
│   │   │   ├── conformal.py                   # Split conformal calibration
│   │   │   ├── ad.py                          # Tanimoto k-NN AD
│   │   │   ├── ensemble.py                    # Weighted combination of baselines + Chemprop
│   │   │   ├── evaluate.py                    # Metrics, calibration, per-class breakdown
│   │   │   ├── compound_classes.py            # SMARTS-based agrochemical class tagging
│   │   │   └── io.py                          # Checkpoint IO with provenance
│   │   ├── endpoints/
│   │   │   ├── __init__.py
│   │   │   ├── bee_oral/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   ├── train.py
│   │   │   │   └── card.py
│   │   │   ├── bee_contact/
│   │   │   ├── fish/
│   │   │   ├── daphnia/
│   │   │   ├── algae/
│   │   │   ├── earthworm/
│   │   │   └── bird/
│   │   └── tests/
│   │       ├── test_baselines.py
│   │       ├── test_chemprop_wrapper.py
│   │       ├── test_conformal.py
│   │       └── test_ad.py
│   └── edeon_models/                          # MODIFIED (Phase 0 package)
│       ├── backends/
│       │   └── trained/                       # NEW under existing backends/
│       │       ├── __init__.py
│       │       ├── tier1_backend.py           # Generic T1 backend class
│       │       └── checkpoints/               # Symlink or path config to data/checkpoints
│       └── overlay/                           # NEW
│           ├── __init__.py
│           ├── lookup.py                      # InChIKey → experimental value
│           └── service.py                     # Attaches experimental value to predictions
├── data/
│   └── checkpoints/                           # NEW
│       └── <endpoint>/v1.0/
│           ├── baselines/
│           │   ├── rf.pkl
│           │   ├── xgb.pkl
│           │   └── hpo_results.json
│           ├── chemprop/
│           │   ├── seed_0/
│           │   ├── seed_1/
│           │   ├── seed_2/
│           │   ├── seed_3/
│           │   ├── seed_4/
│           │   └── ensemble_config.yaml
│           ├── calibration.npz                # Conformal quantile + cal residuals
│           ├── ad_fingerprints.npz            # Training set FPs for k-NN
│           ├── ensemble_weights.yaml          # Weighted-combination weights
│           ├── manifest.json
│           ├── model_card.yaml
│           └── validation_report.html         # Human-readable performance report
├── docs/
│   ├── PHASE2_NOTES.md                        # NEW — deviation log
│   ├── PHASE2_VALIDATION_PROTOCOL.md          # NEW — methodology document
│   └── TIER1_MODEL_CARDS/                     # NEW — published model cards (per endpoint)
└── .github/
    └── workflows/
        └── tier1_regression.yml               # NEW — CI for T1 model regression
```

`data/checkpoints/` is gitignored by default (large files). A separate sync script (Task E1) handles distribution.

---

## 4. Modeling Methodology Standards

Implement these standards once in `shared/` and apply uniformly across endpoints.

### 4.1 Featurization

Two feature representations used in parallel:

**For baseline models** (`shared/featurize.py`):
- RDKit 2D descriptors: filtered subset (~150 descriptors after removing high-correlation pairs r > 0.95)
- Morgan fingerprints: radius=2, nBits=2048 (default), plus radius=3 nBits=2048 as ensemble diversity
- MACCS keys: 166 bits
- Concatenated to ~2,400 features per compound

```python
def featurize_for_baseline(smiles_list: list[str]) -> np.ndarray:
    """Returns (n_compounds, n_features) array. NaN rows for parse failures."""
```

**For Chemprop**:
- Raw SMILES (Chemprop builds graphs internally)
- No additional featurization

### 4.2 Baseline training (`shared/baselines.py`)

For each endpoint, train two baselines: Random Forest and XGBoost.

**Hyperparameter optimisation**: Optuna with `TPESampler`, 50 trials, scaffold-stratified 5-fold CV on the train partition only. Objective: minimise mean fold RMSE (regression) or maximise mean fold balanced accuracy (classification).

```python
RF_SEARCH_SPACE = {
    "n_estimators": (100, 500),
    "max_depth": (5, 30),
    "min_samples_leaf": (1, 10),
    "min_samples_split": (2, 20),
    "max_features": ["sqrt", "log2", 0.3, 0.5],
}

XGB_SEARCH_SPACE = {
    "n_estimators": (100, 1000),
    "max_depth": (3, 12),
    "learning_rate": (0.01, 0.3),
    "reg_alpha": (0.0, 10.0),
    "reg_lambda": (0.0, 10.0),
    "subsample": (0.6, 1.0),
    "colsample_bytree": (0.6, 1.0),
}
```

After HPO, refit on the full train partition with the best hyperparameters. Save with pickle + a JSON sidecar containing hyperparameters and HPO history.

### 4.3 Chemprop ensemble (`shared/chemprop_wrapper.py`)

Train **5 Chemprop D-MPNN models** with seeds [0, 1, 2, 3, 4]. Each model uses the same architecture and hyperparameters, only random initialisation differs.

**Default Chemprop config:**
```yaml
# python/edeon_train/shared/chemprop_default.yaml
depth: 3
hidden_size: 300
ffn_num_layers: 2
ffn_hidden_size: 300
dropout: 0.0
activation: ReLU
aggregation: mean
batch_size: 50
epochs: 50
warmup_epochs: 2
init_lr: 1e-4
max_lr: 1e-3
final_lr: 1e-4
metric: rmse  # for regression
```

**Per-endpoint HPO** (one round, then frozen for all 5 seeds): use Optuna with 20 trials over `{depth, hidden_size, dropout, ffn_num_layers}` on the train partition with scaffold-stratified 3-fold CV. Apply the best config to all 5 seeds. Document chosen hyperparameters in the endpoint config.yaml.

**Ensemble prediction**: arithmetic mean of the 5 seeds' outputs. Ensemble variance is recorded for UQ ensemble member (used in calibration audit, not directly as the user-facing CI).

```python
def train_chemprop_ensemble(
    train_smiles: list[str],
    train_y: np.ndarray,
    config: dict,
    output_dir: Path,
    seeds: list[int] = [0, 1, 2, 3, 4],
) -> None: ...

def predict_chemprop_ensemble(
    smiles: list[str],
    checkpoint_dir: Path,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (mean, std) per compound across the 5 ensemble members."""
```

### 4.4 Final ensemble combination (`shared/ensemble.py`)

The deployed T1 prediction is a weighted average of:
- Baseline RF mean prediction
- Baseline XGBoost mean prediction
- Chemprop ensemble mean prediction

Weights are determined by inverse cross-validation RMSE on the train set:
```
w_i = (1/RMSE_i) / Σ(1/RMSE_j)
```

Record weights in `ensemble_weights.yaml`. The deployed backend reads these at load time.

If one model component is dramatically worse than others (e.g., Chemprop RMSE > 2× the best baseline), drop it from the ensemble. Document the decision in the endpoint config.

### 4.5 Conformal calibration (`shared/conformal.py`)

**Split conformal prediction for regression**:

```python
class SplitConformalRegressor:
    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.quantile_: Optional[float] = None
        self.cal_residuals_: Optional[np.ndarray] = None

    def calibrate(self, y_pred_cal: np.ndarray, y_true_cal: np.ndarray) -> None:
        residuals = np.abs(y_pred_cal - y_true_cal)
        n = len(residuals)
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        q_level = min(q_level, 1.0)
        self.quantile_ = float(np.quantile(residuals, q_level))
        self.cal_residuals_ = residuals

    def interval(self, y_pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.quantile_ is None:
            raise RuntimeError("Must calibrate before predicting intervals")
        return y_pred - self.quantile_, y_pred + self.quantile_

    def empirical_coverage(self, y_pred_held: np.ndarray, y_true_held: np.ndarray) -> float:
        lo, hi = self.interval(y_pred_held)
        in_interval = (y_true_held >= lo) & (y_true_held <= hi)
        return float(in_interval.mean())
```

**Mondrian conformal** (optional refinement): stratify the calibration set by predicted-value quintile, compute a separate quantile per stratum, apply stratum-specific interval at prediction time. Use Mondrian if and only if the split-conformal empirical coverage on the test set deviates from 95% by more than 5 percentage points and Mondrian closes the gap.

**Calibration on Chemprop ensemble variance**: in addition to absolute-residual conformal, fit a second calibrator using *relative* residuals scaled by ensemble standard deviation: `r_i = |y_i - ŷ_i| / max(σ_i, ε)`. This allows ensemble-variance-aware intervals: `CI = ŷ ± q * σ`. Compare against split conformal; deploy whichever achieves better calibration on the held-out cal split.

Save both calibrators in `calibration.npz` with metadata.

### 4.6 Applicability domain (`shared/ad.py`)

Tanimoto k-NN AD as in Phase 0 spec, but with these specifics:
- k = 5
- Fingerprint: Morgan radius 2, 2048 bits
- `in_threshold` = 95th percentile of mean-k-NN distances within the training set
- `out_threshold` = 99th percentile

Save training set fingerprints and thresholds in `ad_fingerprints.npz`. The T1 backend at runtime computes the query's k-NN distance against this saved training set.

### 4.7 Evaluation (`shared/evaluate.py`)

For each model component and the final ensemble, compute:

**Regression metrics**: RMSE, MAE, R², Spearman ρ, Pearson r.

**Calibration metrics**:
- Empirical coverage of 95% CI on cal and test
- Mean interval width
- Calibration curve (predicted CI width vs. observed residual): 10-bin Brier-style histogram

**Per-chemical-class breakdown**: tag each compound using `shared/compound_classes.py` SMARTS-based classifier (see 4.8). Report RMSE and AD-coverage per class.

**Per-split-region breakdown**: report metrics separately for compounds within AD, borderline, and out-of-AD on the test set.

**Output**: per endpoint, generate:
- `validation_report.json` (structured for model card consumption)
- `validation_report.html` (human-readable with calibration plot, parity plot, per-class table)
- Update `model_card.yaml` with all metrics

### 4.8 Compound class tagging (`shared/compound_classes.py`)

SMARTS-based classifier with patterns for the major agrochemistry classes. Implement at minimum:

```python
COMPOUND_CLASS_SMARTS = {
    # Insecticides
    "neonicotinoid": "[#6]-[#7](-[#6]=[#7]/[#7+](=O)[O-])-...",  # simplified
    "organophosphate": "[#15](=[#16,#8])(-[OX2])(-[OX2])-[OX2]",
    "pyrethroid": "C1CC1(C(=O)O[#6])",  # cyclopropane carboxylate
    "carbamate": "[#7]-C(=O)-O-[#6]",
    "diamide": "C(=O)[NH][#6]C(=O)[NH]",
    # Fungicides
    "triazole": "n1cncn1",
    "strobilurin": "C/C(=C/O[#6])C(=O)OC",  # methoxyacrylate
    "sdhi": "[#6]-C(=O)-[NH]-c1ccccc1",  # carboxamide (loose)
    # Herbicides
    "sulfonylurea": "S(=O)(=O)N(C(=O)N([#6])[#7])",
    "phenoxyacid": "Oc1ccccc1OC(=O)",  # loose
    "imidazolinone": "N1C(=O)C(C)(C)NC1=N",
    "triazine": "n1c(N)nc(N)nc1",
}


def tag_compound_classes(smiles: str) -> list[str]:
    """Return list of matched class tags (compound may match multiple)."""
```

If no class matches, tag as `"unclassified"`. Document the SMARTS list in `docs/PHASE2_VALIDATION_PROTOCOL.md`. These are intentionally approximate — the goal is to enable per-class performance breakdown, not perfect IRAC/HRAC/FRAC reproduction. The agent may improve SMARTS but should not block on perfection.

---

## 5. Per-Endpoint Specifications

Each endpoint has a `config.yaml` defining endpoint-specific decisions. The template is given here; each endpoint overrides as needed.

```yaml
# python/edeon_train/endpoints/<endpoint>/config.yaml
endpoint: bee_acute_oral_ld50
phase1_dataset: data/curated/bee_acute_oral_ld50/v1.0
target_column: value_log               # Train on log-transformed value
target_kind: regression
primary_split: scaffold                 # Headline metric source
additional_splits: [random, time]      # Also report on these
calibration_split: scaffold/cal
test_split: scaffold/test
baseline_models: [random_forest, xgboost]
include_chemprop: true
chemprop:
  hpo_trials: 20
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 50
  patience: 10
ad:
  k: 5
  fp_radius: 2
  fp_bits: 2048
conformal:
  alpha: 0.05
  method: split                         # "split" or "mondrian"
  ensemble_variance_calibration: true   # Try second calibrator
performance_targets:
  rmse_log: 0.65                        # Endpoint-specific aspiration
  r2: 0.65
  ad_coverage_test: 0.6                 # ≥60% of test in AD is target
deployment:
  endpoint_id: bee_acute_oral_ld50       # Maps to Phase 0 Endpoint enum
  tier: 1
  fallback_to_tier: 2
```

### Per-endpoint overrides

| Endpoint | Notes |
|---|---|
| `bee_acute_oral_ld50` | Uses ApisTox time-split (primary), then scaffold for additional reporting. Performance target: RMSE 0.65 log. |
| `bee_acute_contact_ld50` | Same training procedure, separate dataset and checkpoint. |
| `fish_acute_lc50` | Multispecies. Add `species` as auxiliary input feature for Chemprop (one-hot of 6 species). Targets: RMSE 0.70 log, R² 0.55. |
| `daphnia_acute_ec50` | Single-species. Targets: RMSE 0.65 log, R² 0.65. |
| `algae_growth_ec50` | **New endpoint — first time in production.** Smaller dataset (~1500). Targets: R² 0.55, AD coverage 50%. |
| `earthworm_acute_lc50` | ~1000 compounds. Soil-mediation not captured in features — note explicitly in card known_failure_modes. Targets: R² 0.60. |
| `bird_acute_oral_ld50` | Smallest dataset (~600). Pool quail + mallard with species as feature. Set conservative HPO bounds to avoid overfit. Targets: R² 0.55, AD coverage 40% (deliberately small AD). |

The performance targets are aspirational. Phase 2 ships whatever the model actually achieves, with the gap from target explicitly documented in the validation report.

---

## 6. Task Manifest

---

### Group A — Shared Training Infrastructure

#### Task A1: Project scaffolding
**Depends on:** Phase 0 + Phase 1 merged.
**Files:** Create `python/edeon_train/` directory tree from Section 3. Add to project setup. Define entry point `edeon-train` in `pyproject.toml`.
**Acceptance:** `python -c "import edeon_train"` succeeds. `edeon-train --help` prints usage.

---

#### Task A2: Test-set protection gate
**Depends on:** A1.
**File:** `python/edeon_train/gates.py`

```python
class TestSetGate:
    """Global gate preventing accidental test-set evaluation.

    A separate gate per endpoint. Loading the test split increments a counter;
    the test split may only be loaded if the gate is explicitly opened.
    """

    _registry: dict[str, "TestSetGate"] = {}

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self._opened = False
        self._evaluations = 0
        TestSetGate._registry[endpoint] = self

    def open(self, reason: str) -> None:
        """Open the gate for final evaluation only."""
        if self._evaluations > 0:
            raise RuntimeError(
                f"Test set for {self.endpoint} already evaluated {self._evaluations} times. "
                f"Refusing to re-evaluate. Reason logged: {reason}"
            )
        self._opened = True

    def load_test(self, loader_fn) -> Any:
        if not self._opened:
            raise RuntimeError(
                f"Test set for {self.endpoint} access blocked. Use gate.open() first. "
                f"This is a hard guard against test-set contamination."
            )
        self._evaluations += 1
        self._opened = False  # Auto-close after one access
        return loader_fn()
```

Every endpoint training script obtains its gate via `gates.get(endpoint)` and uses `gate.load_test(...)` to access the test partition.

**Acceptance:** Unit test demonstrating that double-opening raises; that loading test without opening raises.

---

#### Task A3: Featurization module
**Depends on:** A1.
**File:** `python/edeon_train/shared/featurize.py`
**Action:** Implement per Section 4.1:
- `featurize_for_baseline(smiles_list)` returning concatenated descriptor + fingerprint arrays.
- `compute_morgan_fps(smiles_list, radius=2, nbits=2048)` as a standalone (used by AD module too).
- A `FeatureRegistry` class that records which features were computed for reproducibility.

Use ChEMBL Structure Pipeline–standardised SMILES (already canonicalised by Phase 1). Do not re-standardise.

**Acceptance:** Featurising 20 known compounds reproduces expected feature counts. NaN handling for parse failures (rare since Phase 1 already curated).

---

#### Task A4: Baseline training module
**Depends on:** A1, A3.
**File:** `python/edeon_train/shared/baselines.py`
**Action:**

```python
def train_baseline_with_hpo(
    X_train: np.ndarray,
    y_train: np.ndarray,
    train_scaffolds: list[str],
    model_type: Literal["rf", "xgb"],
    search_space: dict,
    n_trials: int = 50,
    cv_folds: int = 5,
    random_state: int = 42,
) -> tuple[BaseEstimator, dict]:
    """
    HPO via Optuna with scaffold-stratified k-fold CV on train data only.
    Returns the refit best model and HPO metadata dict.
    """

def evaluate_baseline_cv(
    model: BaseEstimator,
    X: np.ndarray,
    y: np.ndarray,
    scaffolds: list[str],
    cv_folds: int = 5,
) -> dict:
    """Return per-fold and aggregate CV metrics."""
```

Use Optuna's `optuna.integration.OptunaSearchCV` or a custom loop. Persist Optuna study to `data/checkpoints/<endpoint>/v1.0/baselines/hpo_results.json`.

**Acceptance:** Trains RF and XGB on a synthetic regression task, returns sensible models with HPO history. Unit test in `tests/test_baselines.py`.

---

#### Task A5: Chemprop wrapper
**Depends on:** A1.
**File:** `python/edeon_train/shared/chemprop_wrapper.py`
**Action:**

```python
def train_chemprop_ensemble(
    train_smiles: list[str],
    train_y: np.ndarray,
    cal_smiles: list[str],     # Used for early-stopping validation
    cal_y: np.ndarray,
    config: dict,
    output_dir: Path,
    seeds: list[int] = [0, 1, 2, 3, 4],
    auxiliary_features: Optional[np.ndarray] = None,  # For species etc.
) -> dict:
    """
    Train 5 Chemprop D-MPNN models with different seeds.
    Returns dict with per-seed val metrics and ensemble val metrics.
    """

def chemprop_hpo(
    train_smiles: list[str],
    train_y: np.ndarray,
    scaffolds: list[str],
    n_trials: int = 20,
    cv_folds: int = 3,
) -> dict:
    """One-shot HPO on the architecture; returns best config dict."""

def predict_chemprop_ensemble(
    smiles: list[str],
    checkpoint_dir: Path,
    auxiliary_features: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (mean, std) per compound."""
```

Use Chemprop's Python API. If the installed version is 2.x (PyTorch Lightning), use the new `train.run_training` / `MoleculeModel` API. If 1.x, use the legacy CLI invocation through subprocess. Document which version was used in `PHASE2_NOTES.md`.

**Acceptance:** Trains a 5-seed ensemble on a 100-compound synthetic regression task. Ensemble predictions averaged correctly. Saved checkpoints reload cleanly.

---

#### Task A6: Conformal calibration module
**Depends on:** A1.
**File:** `python/edeon_train/shared/conformal.py`
**Action:** Implement `SplitConformalRegressor` per Section 4.5. Add Mondrian variant `MondrianConformalRegressor`. Add `EnsembleVarianceCalibrator` for variance-aware intervals. Implement coverage diagnostics.

**Acceptance:** On a synthetic Gaussian regression task with known residual distribution, calibrated 95% intervals achieve empirical coverage between 92% and 98% on held-out data.

---

#### Task A7: AD module
**Depends on:** A3.
**File:** `python/edeon_train/shared/ad.py`
**Action:** Refactor / reuse the Phase 0 `TanimotoKNN_AD` if it already lives in `edeon_models/ad/`. Add training-time threshold calibration (95th and 99th percentile of intra-training distances) and save/load to/from `.npz`.

```python
class TrainedTanimotoAD:
    @classmethod
    def from_training_smiles(cls, smiles: list[str], k: int = 5,
                             radius: int = 2, nbits: int = 2048) -> "TrainedTanimotoAD":
        """Fit AD on training set."""

    def save(self, path: Path) -> None:
        """Save fingerprints + thresholds to .npz."""

    @classmethod
    def load(cls, path: Path) -> "TrainedTanimotoAD":
        """Load from .npz."""

    def score(self, smiles: list[str]) -> list[tuple[ADStatus, float]]:
        """Score query compounds."""
```

**Acceptance:** Round-trip save/load preserves predictions exactly.

---

#### Task A8: Ensemble combination
**Depends on:** A4, A5.
**File:** `python/edeon_train/shared/ensemble.py`
**Action:**

```python
class WeightedEnsemble:
    """Combines baseline + Chemprop predictions with CV-derived weights."""

    def __init__(self, components: dict[str, BaseEstimator | Path], weights: dict[str, float]):
        ...

    @classmethod
    def from_cv_metrics(cls, components, cv_rmses: dict[str, float]) -> "WeightedEnsemble":
        """Construct weights as inverse-RMSE normalised."""

    def predict(self, smiles: list[str], features: np.ndarray) -> np.ndarray:
        """Weighted mean across components."""

    def save(self, path: Path) -> None:
        """Save weights yaml + component checkpoints (or paths)."""

    @classmethod
    def load(cls, path: Path) -> "WeightedEnsemble":
        ...
```

**Acceptance:** Weights normalise to 1.0. Predictions match manually-computed weighted mean.

---

#### Task A9: Evaluation module
**Depends on:** A8.
**File:** `python/edeon_train/shared/evaluate.py`
**Action:** Implement all metrics from Section 4.7. Generate JSON and HTML reports. HTML report uses a simple Jinja2 template under `python/edeon_train/templates/validation_report.html.j2` with: parity plot, calibration plot, per-class table, AD breakdown.

**Acceptance:** Run on a synthetic regression task and verify the report renders.

---

#### Task A10: Compound class tagger
**Depends on:** A1.
**File:** `python/edeon_train/shared/compound_classes.py`
**Action:** Implement per Section 4.8. Bundle a YAML file `compound_class_smarts.yaml` listing all patterns with citations to IRAC/HRAC/FRAC where applicable.

**Acceptance:** Tagging 30 known marketed pesticides produces the expected class labels for at least 80% of cases (the agent's responsibility is the implementation, not chemical-class perfection).

---

#### Task A11: CLI
**Depends on:** A1.
**File:** `python/edeon_train/cli.py`
**Action:**

```
edeon-train <endpoint> hpo            # HPO only
edeon-train <endpoint> train          # Train baselines + Chemprop
edeon-train <endpoint> calibrate      # Conformal + AD
edeon-train <endpoint> evaluate       # Final test eval (opens gate)
edeon-train <endpoint> deploy         # Register T1 backend
edeon-train <endpoint> all            # Full pipeline
edeon-train --list                    # List endpoints
edeon-train --status                  # Show what's trained vs. not
```

**Acceptance:** CLI works for all 7 endpoint identifiers (bee_oral, bee_contact, fish, daphnia, algae, earthworm, bird).

---

### Group B — Per-Endpoint Training

Apply the same template to all 7 endpoints. The template per endpoint is:

#### Template: Endpoint `<EP>`
- **Bn.1**: Create `python/edeon_train/endpoints/<EP>/config.yaml` with endpoint-specific settings.
- **Bn.2**: Implement `python/edeon_train/endpoints/<EP>/train.py` orchestrating: load Phase 1 data → featurize → HPO baselines → train baselines → HPO Chemprop → train Chemprop ensemble → save all checkpoints. Does NOT touch test set.
- **Bn.3**: Run `edeon-train <EP> train` end-to-end. Save outputs to `data/checkpoints/<EP>/v1.0/`.
- **Bn.4**: Run `edeon-train <EP> calibrate` to fit conformal calibrator on `cal` split and AD on training set.
- **Bn.5**: Run `edeon-train <EP> evaluate` to evaluate on test set (gate opens once). Generate validation report.
- **Bn.6**: Implement `card.py` to build `model_card.yaml` from training metadata, performance metrics, AD definition. Save to `data/checkpoints/<EP>/v1.0/model_card.yaml` and write a copy to `docs/TIER1_MODEL_CARDS/<EP>.md`.
- **Bn.7**: Verify acceptance criteria: model card complete, calibration coverage in [0.90, 0.98], AD coverage on test set within expectation, no test set contamination.

#### Endpoint task list

- **Task B1**: bee_acute_oral_ld50
- **Task B2**: bee_acute_contact_ld50
- **Task B3**: fish_acute_lc50
- **Task B4**: daphnia_acute_ec50
- **Task B5**: algae_growth_ec50 (note: new endpoint, no T2 exists — T1 deploys cold)
- **Task B6**: earthworm_acute_lc50
- **Task B7**: bird_acute_oral_ld50

Each task may be parallelised; they share infrastructure but train on different data. **Run bee_oral first** (B1) — it has the cleanest data (ApisTox time-split provided) and reveals any infrastructure problems early.

**Per-endpoint acceptance**:
- Calibration empirical coverage on cal split: [0.93, 0.97].
- Calibration empirical coverage on test split: [0.90, 1.00] (looser).
- AD coverage of test set ≥ endpoint config's `performance_targets.ad_coverage_test`.
- Validation report HTML renders.
- Model card has all required fields populated.
- Test gate evaluated exactly once.

---

### Group C — T1 Backend Implementations

#### Task C1: Generic T1 backend
**Depends on:** All B-tasks complete for at least one endpoint.
**File:** `python/edeon_models/backends/trained/tier1_backend.py`
**Action:**

```python
class TrainedTier1Backend(ModelBackend):
    """Generic Tier-1 backend loading checkpoints produced by edeon_train."""

    def __init__(self, endpoint: Endpoint, checkpoint_dir: Path):
        self._endpoint = endpoint
        self._dir = checkpoint_dir
        self._load()

    def _load(self):
        """Load:
          - WeightedEnsemble from ensemble_weights.yaml + component checkpoints
          - SplitConformalRegressor (or Mondrian) from calibration.npz
          - TrainedTanimotoAD from ad_fingerprints.npz
          - ModelCard from model_card.yaml
        """

    def endpoint(self) -> Endpoint:
        return self._endpoint

    def tier(self) -> int:
        return 1

    def version(self) -> str:
        return self._card.version

    def predict(self, smiles: list[str], conditions=None) -> list[Prediction]:
        # 1. Featurize for baseline + Chemprop in parallel
        # 2. Ensemble predict
        # 3. Apply conformal interval
        # 4. Apply AD scoring
        # 5. Construct Prediction objects with tier=1
        ...

    def applicability_domain(self, smiles: list[str]) -> list[ADStatus]:
        ...

    def metadata(self) -> ModelCard:
        return self._card
```

Inference path must:
- Apply Phase 1 standardisation (canonical SMILES) if input is non-canonical — keep predictions consistent.
- Skip non-parsable SMILES and return `Prediction` with `value=NaN`, `ad_status=UNKNOWN`, warning `["parse_failed"]`.
- For numeric endpoints, populate `value_log` and `value` (back-transform to native units).
- For each prediction, write a per-call provenance entry including `model_id`, `model_version`, `component_predictions` (RF, XGB, Chemprop), `ensemble_weights`, `conformal_quantile`, `ad_nn_distance`.

**Acceptance:** Loading a B1 (bee oral) checkpoint and predicting on 5 known compounds returns valid `Prediction` objects with non-trivial CIs and non-UNKNOWN AD status.

---

#### Task C2: Register T1 backends in registry
**Depends on:** C1, all B-tasks complete.
**File:** Extend `edeon_models/__init__.py` `build_default_registry()`:

```python
def build_default_registry() -> BackendRegistry:
    reg = BackendRegistry()
    # ... existing T2 registrations ...

    # T1 registrations: load whichever endpoints have completed checkpoints
    from .backends.trained import TrainedTier1Backend
    checkpoint_root = Path("data/checkpoints")
    for endpoint in Endpoint:
        ep_dir = checkpoint_root / endpoint.value / "v1.0"
        if ep_dir.exists() and (ep_dir / "model_card.yaml").exists():
            try:
                backend = TrainedTier1Backend(endpoint, ep_dir)
                reg.register(backend)
            except Exception as e:
                logger.warning(f"Failed to load T1 backend for {endpoint}: {e}")

    return reg
```

**Acceptance:** After B1 completes, `reg.get(Endpoint.BEE_ACUTE_ORAL_LD50)` returns the T1 backend (not the T2 LogP fallback). Manually removing the checkpoint reverts to T2.

---

#### Task C3: Persist T1 ModelCards
**Depends on:** C2.
**Action:** Extend the same startup function to persist each T1 backend's model card to SQLite via Phase 0's `save_card()` (table `model_cards`).

**Acceptance:** SQLite contains both T2 and T1 cards. Frontend ModelCardViewer can open T1 cards.

---

### Group D — Experimental Value Overlay

#### Task D1: Build InChIKey index
**Depends on:** Phase 1 datasets exist.
**File:** `python/edeon_models/overlay/lookup.py`

```python
class ExperimentalValueIndex:
    """In-memory lookup from InChIKey → list of measured values across endpoints.

    Loaded at startup from the Phase 1 curated/*/v1.0/curated.parquet files.
    """

    def __init__(self):
        self._index: dict[tuple[str, str], list[dict]] = {}  # (inchikey, endpoint) → [{value, source, citation}]

    @classmethod
    def build(cls, curated_root: Path) -> "ExperimentalValueIndex":
        """Walk data/curated/*/v1.0/ and build the index."""

    def lookup(self, inchikey: str, endpoint: Endpoint) -> list[dict]:
        """Return list of experimental values for this compound/endpoint pair."""

    def lookup_smiles(self, smiles: str, endpoint: Endpoint) -> list[dict]:
        """Convenience: standardise SMILES to InChIKey then lookup."""
```

**Acceptance:** After loading all Phase 1 datasets, looking up known marketed pesticides (e.g., imidacloprid, glyphosate, azoxystrobin) returns their expected experimental values.

---

#### Task D2: Overlay service
**Depends on:** D1.
**File:** `python/edeon_models/overlay/service.py`

```python
class OverlayService:
    """Attaches experimental values to Prediction provenance when available."""

    def __init__(self, index: ExperimentalValueIndex):
        self._index = index

    def enrich(self, predictions: list[Prediction]) -> list[Prediction]:
        """For each prediction, check the index and attach matches to provenance."""
```

Integration point: in the Python IPC server (Phase 0 Task E5), wrap every `predict()` call with `OverlayService.enrich()` before returning to the Rust core.

**Acceptance:** A prediction for imidacloprid against `bee_acute_oral_ld50` returns a Prediction object whose provenance contains an `experimental_values` array with the ApisTox value.

---

#### Task D3: Frontend experimental value display
**Depends on:** D2, Phase 0 frontend components.
**File:** Extend `src/components/models/PredictionDisplay.tsx`.

When a prediction's provenance contains `experimental_values`, render an additional row beneath the prediction:

```
Predicted: 8.4 µg/bee  [3.1 – 22.8]  [T1]  [In domain]
🧪 Measured: 7.2 µg/bee (ApisTox, Adamczyk et al. 2025)
```

Click the experimental row opens a small popover with full citation and source link.

**Acceptance:** For at least 5 marketed pesticides, the experimental value displays correctly. Frontend gracefully handles predictions without experimental values (no UI artefact).

---

### Group E — Integration, Validation, and CI

#### Task E1: Checkpoint distribution
**Depends on:** B-tasks complete.
**Action:** `data/checkpoints/` is gitignored. Provide:
- `scripts/sync_checkpoints.sh` — pushes/pulls checkpoints to/from a configured remote (S3, HuggingFace Hub, or Zenodo). The agent should not implement actual remote credentials; provide a stub that documents the contract and uses environment variables.
- `scripts/verify_checkpoints.sh` — checks SHA-256 against `data/checkpoints/MANIFEST.json`.

Build `data/checkpoints/MANIFEST.json` listing every endpoint with version, SHA-256 of each artefact, and total size.

**Acceptance:** Verify script flags tampered files.

---

#### Task E2: Tier-1 regression CI
**Depends on:** B1 complete (at minimum), C1, C2.
**File:** `.github/workflows/tier1_regression.yml`

```yaml
name: Tier-1 Model Regression
on: [push, pull_request]
jobs:
  t1_smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Restore checkpoints
        run: ./scripts/sync_checkpoints.sh pull
      - name: Run T1 smoke tests
        run: pytest tests/regression/test_t1_smoke.py -v
```

`test_t1_smoke.py` loads each available T1 backend, predicts on a fixed 20-compound reference set, asserts predictions are within tolerance of stored expected values (similar to Phase 0 regression harness). Tolerances stored in `tests/regression/tier1_tolerance.yaml`.

**Acceptance:** CI runs and reports per-endpoint pass/fail.

---

#### Task E3: End-to-end integration test
**Depends on:** C1, C2, D2, frontend updates.
**File:** `tests/integration/test_t1_e2e.py`

Test that:
1. Loads the registry at startup.
2. For bee oral, asserts `reg.get(Endpoint.BEE_ACUTE_ORAL_LD50).tier() == 1`.
3. Predicts on imidacloprid SMILES.
4. Asserts: prediction has CI, AD status (in/borderline/out, not unknown), tier=1, provenance contains experimental values.

**Acceptance:** Test passes.

---

#### Task E4: Documentation
**Depends on:** All B-tasks complete.
**File:** `docs/PHASE2_VALIDATION_PROTOCOL.md`

Comprehensive methodology document describing:
- Featurization choices
- HPO procedure
- Chemprop ensemble protocol
- Conformal calibration method
- AD definition
- Test set protection
- Per-endpoint specifics
- Per-class breakdown methodology

This document is the methods section for Paper 3.

**Acceptance:** Document exists, complete, internally consistent.

---

#### Task E5: Validation report aggregation
**Depends on:** B-tasks complete.
**File:** `docs/PHASE2_BENCHMARK_RESULTS.md`

Auto-generated table summarising every endpoint:

| Endpoint | n_train | n_cal | n_test | Scaffold RMSE | R² | Coverage(95%) | AD coverage test |
|---|---|---|---|---|---|---|---|

Plus a per-endpoint subsection linking to its validation report HTML.

**Acceptance:** Document exists and reflects current trained models.

---

## 7. Acceptance Criteria for Phase 2 Complete

Phase 2 is complete when ALL of the following hold:

1. Shared infrastructure (Group A) implemented and tested.
2. For each of the 7 endpoints (B1–B7):
   - Trained baselines (RF + XGB) and Chemprop ensemble (5 seeds) exist at `data/checkpoints/<endpoint>/v1.0/`.
   - Conformal calibrator fit on cal split; empirical 95% coverage on cal in [0.93, 0.97].
   - Tanimoto k-NN AD with calibrated 95th/99th percentile thresholds.
   - Final test set evaluation performed exactly once; results in `validation_report.html` and `model_card.yaml`.
   - Model card complete: training data, performance, AD definition, known failure modes, references.
3. T1 backends register on startup and take precedence over T2 LogP backends in the registry.
4. Calling `model_predict` for any of the 7 endpoints returns Tier-1 predictions with CIs and AD status.
5. Experimental-value overlay attaches measured values to predictions where the InChIKey matches a curated dataset record.
6. Frontend displays experimental values alongside predictions.
7. Tier-1 regression CI passes.
8. `PHASE2_VALIDATION_PROTOCOL.md` and `PHASE2_BENCHMARK_RESULTS.md` are populated.
9. `PHASE2_NOTES.md` documents deviations and decisions.

---

## 8. Out of Scope (for Phase 2)

Do **not** in Phase 2:

- Train models for non-ecotox endpoints (rat LD50, skin sensitization, Koc, DT50, BCF) — those are Phase 3 / Phase 4.
- Modify Phase 0 interfaces or Phase 1 datasets.
- Implement selectivity prediction (Paper 2 / Phase 5).
- Build the Knowledge Hub beyond the experimental-value overlay (overlay is a minimal slice of the Hub vision).
- Train any model on the test set.
- Replace the QSAR Studio (T4 backends still work as before).
- Implement model retraining pipelines or scheduled drift detection.
- Add multi-task learning, transfer learning, or pretrained chemistry models (could be Phase 5+).
- Implement federated learning for proprietary customer data.
- Touch UV photostability, 3D viewer docking, or bioisostere engine (Phase 5 / 6).

If the agent identifies a blocker requiring scope expansion, document and stop.

---

## 9. Risk and Mitigation

| Risk | Mitigation |
|---|---|
| Bird endpoint (~600 compounds) overfits | Use conservative HPO bounds; report AD coverage; accept lower target |
| Chemprop fails to install or train (PyTorch version conflicts) | Document fallback: use baselines only, mark Chemprop as `not_available` in card. Document in PHASE2_NOTES. |
| Conformal coverage badly miscalibrated (< 0.85 or > 0.99) | Try Mondrian stratified conformal; if still bad, fall back to nonparametric bootstrap; document in card under "known failure modes" |
| Calibration set has poor coverage of test region | Report AD coverage of cal vs. test; if cal AD < test AD significantly, flag |
| Test set contamination | Test gate (A2) blocks; CI verifies; manual audit of training scripts during code review |
| Experimental overlay matches noise (random InChIKey collisions for very small molecules) | Drop overlay matches for compounds where size(<5 heavy atoms) or where Phase 1 record carries `quality_flags=["censored_*"]` |
| Frontend overload (showing too many experimental values) | Cap at the 3 most recent / highest-quality records per endpoint per compound |

---

## 10. Conventions

- Random seeds: 42 for splits, [0,1,2,3,4] for Chemprop ensemble.
- Naming: `snake_case` Python; endpoint identifiers from `Endpoint` enum.
- Logging: `logging.getLogger("edeon_train")` and `edeon_train.<endpoint>` per endpoint.
- File formats: pickle for sklearn (with `protocol=4`), PyTorch state-dict for Chemprop, npz for arrays, yaml for configs and cards, parquet for data, json for structured logs.
- Timestamps: UTC ISO 8601.
- Hashing: SHA-256 over canonical-ordered bytes.

---

## 11. Phase 2 → Future Handoff

Phase 2 outputs feed:

- **Phase 3** (mammalian tox + sensitisation) — applies the same training recipe to rat LD50, skin sensitisation, etc., using Phase 1 datasets.
- **Phase 4** (environmental fate) — same recipe with modifications for the probabilistic DT50 model (Gnann-style variance modelling).
- **Paper 3** (Open Benchmarks for Pesticide Ecotoxicity Prediction) — the validation reports, model cards, and curated datasets together form the publication.
- **Commercial pitch** — the per-endpoint validation reports become the customer-facing performance documentation; the model cards become the "How are predictions made?" explainer in the app.

The deliverables of Phase 2 are designed to be re-trainable by external researchers from the curated datasets + this specification — that is the meaning of "reproducible reference models."

---

## 12. Deviation Log

Maintain `docs/PHASE2_NOTES.md` recording:
- Chemprop version used and any installation workarounds.
- GPU availability and runtime per endpoint.
- Endpoints where HPO converged poorly (and the action taken).
- Endpoints where conformal calibration required Mondrian or bootstrap.
- Compounds flagged as overlay-match noise and the cutoff applied.
- Any departure from default ensemble weights and the rationale.
- Final test-set timestamps (proves the test gate fired exactly once per endpoint).

---

**End of Phase 2 Specification.**
