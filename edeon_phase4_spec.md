# Edeon Phase 4 — Mammalian Tox & Sensitization Tier-1 Model Implementation Specification

**Audience:** coding agent.
**Goal:** train Tier-1 reference models for the four mammalian/sensitization endpoints — rat acute oral LD50 (regression + GHS classification), skin sensitization (binary + 4-class), Ames mutagenicity (binary, new endpoint), and the honest redesign of eye irritation as a structural-alerts panel rather than a fake numeric prediction. Deploy as the new backend for the toxicity panel UI.

**Inputs:**
- Phase 1 curated datasets at `data/curated/rat_acute_oral_ld50/v1.0/` and `data/curated/skin_sensitization/v1.0/`.
- Phase 2 shared infrastructure for regression endpoints.
- Phase 3's heteroscedastic infrastructure is NOT needed here — Phase 4 uses standard regression for rat LD50 (CATMoS data doesn't have the multi-record-per-compound structure that justifies Phase 3's complexity).
- Phase 0 architecture (Endpoint enum, ModelBackend interface, registry).

**Outputs:** trained model checkpoints at `data/checkpoints/{rat_acute_oral_ld50, skin_sensitization, mutagenicity_ames}/v1.0/`, a structural alerts module for eye irritation, model cards, validation reports, and toxicity-panel UI updates.

This phase has two methodological additions to the Phase 2 recipe: (1) classification with proper calibration (Platt scaling / isotonic regression) and (2) a structural-alert backend that surfaces qualitative warnings without pretending to be a quantitative model.

---

## 0. Context and Hard Rules

**Hard rule 1: classification calibration is mandatory.**
Every classification backend must output *calibrated probabilities* via Platt scaling or isotonic regression on the held-out cal split. Uncalibrated probabilities from RF/XGBoost are not acceptable for Tier-1. The calibration improvement must be documented in the model card (Brier score, expected calibration error).

**Hard rule 2: eye irritation does NOT get a Tier-1 numeric model.**
The public data is too thin (different test guidelines, inconsistent endpoints across BCOP / Draize / cytotoxicity surrogates) to train a defensible regression. The honest move is:
- Disable the existing Tier-2 LogP-based eye irritation predictor in the default display.
- Replace with a **structural alert panel** that flags compounds matching SMARTS patterns for known eye-irritating chemotypes (aldehydes, epoxides, isocyanates, etc.) with literature citations.
- Document this explicitly as "qualitative screening, not a quantitative prediction."

A T3 EPA T.E.S.T integration is out of scope for Phase 4 but documented as a future option.

**Hard rule 3: mutagenicity is a new endpoint.**
Phase 1 did not curate mutagenicity data. Phase 4 includes a mini-curation step that uses the Phase 1 infrastructure (`edeon_data` package) to fetch, curate, and version the Hansen-Honma Ames dataset before training. The output is a normal Phase 1 v1.0 bundle at `data/curated/mutagenicity_ames/v1.0/`. The Endpoint enum must be extended.

**Hard rule 4: test set protection (same as Phase 2/3).**
Use the `TestSetGate`. Each endpoint's test set is opened exactly once.

**Hard rule 5: classification uses scaffold-stratified splits.**
The Phase 1 datasets already produced scaffold splits. The classification recipe additionally stratifies *within* the scaffold groups by class label to maintain class balance across folds during HPO.

---

## 1. Tech Stack Assumptions

In addition to Phase 2/3:

- **Scikit-learn calibration**: `sklearn.calibration.CalibratedClassifierCV` with `method='sigmoid'` (Platt) or `'isotonic'`
- **imbalanced-learn** (`imblearn`) ≥ 0.12: for optional SMOTE / class weighting variants
- **Mondrian conformal classifiers** (optional): implement directly or use crepes ≥ 0.4
- **Chemprop ≥ 2.0** with `BinaryClassificationFFN` and `MulticlassClassificationFFN` heads
- **RDKit** for the structural alerts module (FilterCatalog or custom SMARTS matching)

No new heavy dependencies vs. Phase 3.

---

## 2. Architectural Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  edeon-train rat_acute_oral_ld50 all     (Phase 2 recipe + classifier head) │
│  edeon-train skin_sensitization all      (classification recipe)            │
│  edeon-data mutagenicity_ames acquire    (mini Phase 1 curation)            │
│  edeon-data mutagenicity_ames all                                           │
│  edeon-train mutagenicity_ames all       (classification recipe)            │
│  edeon-train eye_irritation deploy_alerts (structural-alert backend only)   │
└──────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────────┐
              ▼               ▼                   ▼
    ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │ Regression+      │ │ Classification   │ │ Structural Alerts│
    │  Classification  │ │  endpoints       │ │  (eye irritation)│
    │                  │ │                  │ │                  │
    │ Rat LD50         │ │ Skin sens (4cls) │ │ SMARTS rules     │
    │ (numeric + GHS)  │ │ Ames (binary)    │ │ + literature     │
    │                  │ │ + Platt calib    │ │   citations      │
    └──────────────────┘ └──────────────────┘ └──────────────────┘
                              │                     │
                              ▼                     ▼
                  ┌───────────────────────────────────────────┐
                  │  BackendRegistry                          │
                  │  T1 mammalian backends registered         │
                  │  Eye irritation alerts backend (T1-alt)   │
                  └───────────────────────────────────────────┘
                              │
                              ▼
                  ┌───────────────────────────────────────────┐
                  │  Frontend: Toxicity Panel                 │
                  │  - Rat LD50: 320 mg/kg [120 – 850]  GHS Cat 4 │
                  │  - Skin sens: Weak sensitizer (P=0.34)        │
                  │  - Ames: Negative (P=0.87)                    │
                  │  - Eye alerts: 2 alerts (aldehyde, epoxide)   │
                  └───────────────────────────────────────────┘
```

---

## 3. Repository Layout

```
edeon/
├── python/
│   ├── edeon_models/
│   │   ├── endpoints.py                      # MODIFIED — add MUTAGENICITY_AMES
│   │   └── backends/
│   │       ├── trained/
│   │       │   ├── classification_backend.py # NEW — generic classification T1
│   │       │   └── ... (existing)
│   │       ├── alerts/                       # NEW
│   │       │   ├── __init__.py
│   │       │   ├── alerts_backend.py
│   │       │   ├── rules/
│   │       │   │   └── eye_irritation.yaml
│   │       │   └── ...
│   │       └── ...
│   ├── edeon_train/
│   │   ├── shared/
│   │   │   ├── classification.py             # NEW — RF/XGB/Chemprop classification
│   │   │   ├── probability_calibration.py    # NEW — Platt + isotonic + ECE
│   │   │   └── ...
│   │   ├── endpoints/
│   │   │   ├── rat_acute_oral_ld50/          # NEW
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   ├── train.py                  # Joint regression + classification
│   │   │   │   └── card.py
│   │   │   ├── skin_sensitization/           # NEW
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   ├── train.py
│   │   │   │   └── card.py
│   │   │   ├── mutagenicity_ames/            # NEW
│   │   │   │   ├── __init__.py
│   │   │   │   ├── config.yaml
│   │   │   │   ├── train.py
│   │   │   │   └── card.py
│   │   │   └── eye_irritation/               # NEW (alerts-only, no training)
│   │   │       ├── __init__.py
│   │   │       ├── config.yaml
│   │   │       └── card.py
│   └── edeon_data/                           # EXTENDED — new endpoint module
│       └── endpoints/
│           └── mutagenicity_ames/            # NEW (Phase 1 add-on)
│               ├── __init__.py
│               ├── acquire.py
│               ├── curate.py
│               ├── split.py
│               └── card.py
├── data/
│   ├── curated/
│   │   └── mutagenicity_ames/v1.0/           # NEW — produced by Phase 4 task A4
│   └── checkpoints/
│       ├── rat_acute_oral_ld50/v1.0/
│       ├── skin_sensitization/v1.0/
│       └── mutagenicity_ames/v1.0/
├── docs/
│   ├── PHASE4_NOTES.md
│   ├── PHASE4_CLASSIFICATION_PROTOCOL.md
│   ├── EYE_IRRITATION_ALERTS_RATIONALE.md
│   └── TIER1_MODEL_CARDS/
│       ├── rat_acute_oral_ld50.md
│       ├── skin_sensitization.md
│       ├── mutagenicity_ames.md
│       └── eye_irritation_alerts.md
└── .github/
    └── workflows/
        └── tier1_mammalian_regression.yml
```

---

## 4. Modeling Methodology Standards

### 4.1 Rat acute oral LD50 — regression + classification

The CATMoS dataset supports both:
- **Numeric**: LD50 in mg/kg bw (regression)
- **GHS classification**: Cat 1–5 plus "not classified" (6-way ordinal classification)

Phase 1 curated both `value_log` (regression target) and `value_class` (GHS category).

**Approach**: train *two separate* models, sharing the featurization but with different heads:

1. **Regression model** for numeric LD50: standard Phase 2 recipe (RF + XGB + Chemprop ensemble + split conformal + Tanimoto AD).
2. **Classification model** for GHS category: standard Phase 4 classification recipe (Section 4.2).

The T1 backend returns *both* in the Prediction: the numeric value with CI as the primary `value`, the predicted GHS class in provenance under `ghs_category`, and probability over GHS categories in provenance under `class_probabilities`.

**Why two models, not one ordinal regression**: ordinal regression is technically the correct framework but cross-implementation reproducibility is much worse than two independent models. The two-model approach is what published CATMoS implementations use.

**Performance targets**:
- Regression: RMSE (log mg/kg) ≤ 0.55, R² ≥ 0.60
- Classification: balanced accuracy ≥ 0.70, macro F1 ≥ 0.55, ECE ≤ 0.05

### 4.2 Classification recipe (new — Section 4.2 is the canonical classification methodology)

Applies to skin sensitization, mutagenicity, and the GHS head of rat LD50.

#### 4.2.1 Model components

Train three classifiers per endpoint:
1. **Random Forest** (`sklearn.ensemble.RandomForestClassifier`) with `class_weight='balanced'`.
2. **XGBoost** (`xgboost.XGBClassifier`) with `scale_pos_weight` (binary) or sample weighting (multi-class).
3. **Chemprop** with appropriate classification head.

Use the same featurization as the regression recipe (Phase 2 Section 4.1 — RDKit + Morgan + MACCS for baselines; raw SMILES for Chemprop).

#### 4.2.2 Class imbalance handling

For binary classification, if class imbalance > 3:1 use:
- Default: `class_weight='balanced'` (sklearn) or `scale_pos_weight = n_negative / n_positive` (XGBoost).
- Optional: SMOTE oversampling via `imblearn.over_sampling.SMOTE`, applied to training fold only inside CV. Train both variants if HPO time permits; pick whichever gives better val balanced accuracy.

For multi-class skin sensitization (4 classes, highly imbalanced):
- Use sample weights inversely proportional to class frequency.
- Skip SMOTE for multi-class (less reliable in high-dimensional descriptor space).

#### 4.2.3 Hyperparameter optimization

Same Optuna search spaces as Phase 2 baselines, but:
- Optimisation objective: maximise mean **balanced accuracy** (binary) or **macro F1** (multi-class) on scaffold-stratified, class-stratified 5-fold CV.
- For Chemprop: same architecture HPO as Phase 2, classification head replaces regression head.

#### 4.2.4 Probability calibration

After HPO and ensemble training, calibrate probability outputs on the **cal split**:

```python
# python/edeon_train/shared/probability_calibration.py
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
import numpy as np


def calibrate_probabilities_platt(p_uncal_cal, y_true_cal):
    """Platt (sigmoid) scaling. Returns calibrated probabilities and the model."""
    lr = LogisticRegression()
    lr.fit(p_uncal_cal.reshape(-1, 1), y_true_cal)
    return lr


def calibrate_probabilities_isotonic(p_uncal_cal, y_true_cal):
    """Isotonic regression. Better for larger calibration sets (n > 1000)."""
    ir = IsotonicRegression(out_of_bounds='clip', y_min=0.0, y_max=1.0)
    ir.fit(p_uncal_cal, y_true_cal)
    return ir


def expected_calibration_error(p, y_true, n_bins=10):
    """Computes ECE on a held-out set."""
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (p >= bins[i]) & (p < bins[i+1])
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = p[mask].mean()
        ece += (mask.sum() / len(p)) * abs(bin_acc - bin_conf)
    return float(ece)


def select_best_calibrator(p_uncal_cal, y_true_cal):
    """Try Platt and isotonic, pick whichever has lower ECE on cal."""
    platt = calibrate_probabilities_platt(p_uncal_cal, y_true_cal)
    iso = calibrate_probabilities_isotonic(p_uncal_cal, y_true_cal)

    p_platt = platt.predict_proba(p_uncal_cal.reshape(-1, 1))[:, 1]
    p_iso = iso.predict(p_uncal_cal)

    ece_platt = expected_calibration_error(p_platt, y_true_cal)
    ece_iso = expected_calibration_error(p_iso, y_true_cal)

    return ('isotonic', iso) if ece_iso < ece_platt else ('platt', platt)
```

Save the chosen calibrator alongside the ensemble. For multi-class, calibrate each binary one-vs-rest sub-problem separately then renormalize.

#### 4.2.5 Ensemble combination

Average the predicted *calibrated* probabilities across the three model types (RF + XGB + Chemprop), weighted by inverse CV-log-loss (analogous to Phase 2's inverse RMSE weighting):
```
w_i = (1 / cv_logloss_i) / Σ (1 / cv_logloss_j)
```

Final probability is the weighted mean. Final class is `argmax` of the ensemble probability.

#### 4.2.6 Applicability domain

Same Tanimoto k-NN AD as Phase 2/3. No change.

#### 4.2.7 Evaluation metrics

Primary:
- **Balanced accuracy (BA)** — primary metric for class-imbalanced binary endpoints
- **Macro F1** — primary metric for multi-class endpoints
- **ROC AUC** — diagnostic, not a target

Calibration:
- **ECE** (expected calibration error, 10 bins) — target ≤ 0.05
- **Brier score** — proper scoring rule, report
- Calibration plot (reliability diagram) — visual in validation report

Per-class:
- Precision, recall, F1 per class
- Confusion matrix

Per-chemical-class (using `compound_classes.py` from Phase 2): BA per organophosphate / azole / etc.

AD breakdown: BA inside AD vs. outside AD on test set.

### 4.3 Structural alerts for eye irritation

Implement a SMARTS-based alerts backend. Rules in `python/edeon_models/backends/alerts/rules/eye_irritation.yaml`:

```yaml
# eye_irritation.yaml
version: 1.0
endpoint: eye_irritation_alerts
description: |
  Qualitative structural alerts for eye irritation potential. Each rule maps
  a SMARTS pattern to a category (severe / moderate / mild) with a citation.
  This is NOT a quantitative prediction. Compounds without alerts are NOT
  necessarily non-irritants.

rules:
  - id: aldehyde
    smarts: "[CX3H1](=O)[#6]"
    category: severe
    description: "Aldehydes are highly reactive toward corneal proteins."
    references: ["Verheyen et al. 2017 SAR QSAR Environ Res 28:341"]

  - id: epoxide
    smarts: "[OX2r3]1[CX4r3][CX4r3]1"
    category: severe
    description: "Epoxides are strong electrophiles; reactive toward corneal nucleophiles."
    references: ["Patlewicz et al. 2014 Regul Toxicol Pharmacol 70:629"]

  - id: isocyanate
    smarts: "N=C=O"
    category: severe
    description: "Isocyanates cause severe ocular damage by protein crosslinking."
    references: ["OECD TG 405 Test Guideline"]

  - id: acid_halide
    smarts: "[CX3](=O)[F,Cl,Br,I]"
    category: severe
    description: "Acid halides hydrolyze to strong acids on contact with the eye."
    references: ["OECD 405 Guideline"]

  - id: anhydride
    smarts: "[CX3](=O)[OX2][CX3]=O"
    category: severe
    description: "Anhydrides hydrolyze to acids on the corneal surface."
    references: ["Patlewicz 2014"]

  - id: alpha_beta_unsaturated_carbonyl
    smarts: "[CX3]=[CX3][CX3]=O"
    category: moderate
    description: "Michael acceptor; reactive toward corneal thiols."
    references: ["Schultz et al. 2007 SAR QSAR Environ Res 18:413"]

  - id: peroxide
    smarts: "[OX2][OX2]"
    category: severe
    description: "Peroxides oxidize corneal tissue."
    references: ["Generic toxicological alert"]

  - id: organotin
    smarts: "[#50]"
    category: moderate
    description: "Organotin compounds; documented eye toxicity."
    references: ["EFSA scientific opinions"]

  - id: strong_acid_phenol
    smarts: "[OH][c]([F,Cl,Br,I,N+](=O)=O)"  # halophenols and nitrophenols
    category: moderate
    description: "Strongly acidic phenols cause corneal denaturation."
    references: ["Draize-derived SAR"]

  - id: quaternary_ammonium
    smarts: "[N+](C)(C)(C)C"
    category: moderate
    description: "Cationic surfactants disrupt corneal membranes."
    references: ["Patlewicz 2014"]

  - id: aldehyde_ortho_phenol
    smarts: "[OH]c1ccccc1[CX3H1](=O)"
    category: moderate
    description: "Salicylaldehyde-like structures; documented sensitisers/irritants."
    references: ["Schultz 2007"]
```

The SMARTS patterns are illustrative starting points — verify and refine. The agent should add at least 10 alerts at v1.0 covering the major reactive chemotypes. The exhaustive ECETOC / Cramer-class-style alerts could be added in a v2.0 of this rule file.

**Alerts backend behavior**:
- For a query SMILES, evaluate every SMARTS pattern.
- Return a `Prediction` with `value.categorical = "no_alerts"` if none match, or `"alerts_present"` if any match.
- Provenance contains list of matched alerts with id, category, description, references.
- AD status is always `ADStatus.UNKNOWN` for the alerts backend (no training data).
- Tier: 1-alt (use tier=1 in the registry but mark as "qualitative-only" in the card).

---

## 5. Per-Endpoint Specifications

### 5.1 rat_acute_oral_ld50

```yaml
# config.yaml
endpoint: rat_acute_oral_ld50
phase1_dataset: data/curated/rat_acute_oral_ld50/v1.0
heads:
  regression:
    target_column: value_log
    target_units: log10(mg/kg bw)
    primary_metric: rmse_log
    target: 0.55
  classification:
    target_column: value_class
    classes: ["Cat_1", "Cat_2", "Cat_3", "Cat_4", "Cat_5", "Not_Classified"]
    class_kind: multi_class_ordinal_ish  # treat as multi-class for now
    primary_metric: balanced_accuracy
    target: 0.70
primary_split: scaffold
additional_splits: [random]
calibration_split: scaffold/cal
test_split: scaffold/test
baseline_models: [random_forest, xgboost]
include_chemprop: true
chemprop:
  hpo_trials: 20
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 50
ad:
  k: 5
  fp_radius: 2
  fp_bits: 2048
conformal:                       # Regression CI calibration
  alpha: 0.05
  method: split
probability_calibration:         # Classification calibration
  method: auto                   # Tries Platt and isotonic, picks lower ECE
performance_targets:
  rmse_log: 0.55
  r2: 0.60
  balanced_accuracy: 0.70
  ece: 0.05
  ad_coverage_test: 0.6
deployment:
  endpoint_id: rat_acute_oral_ld50
  tier: 1
  fallback_to_tier: 2
```

### 5.2 skin_sensitization

```yaml
# config.yaml
endpoint: skin_sensitization
phase1_dataset: data/curated/skin_sensitization/v1.0
heads:
  binary:
    target_column: value_class_binary
    classes: ["non_sensitizer", "sensitizer"]
    class_kind: binary
    primary_metric: balanced_accuracy
    target: 0.75
  four_class:
    target_column: value_class_4class
    classes: ["non", "weak", "moderate", "strong"]
    class_kind: multi_class
    primary_metric: macro_f1
    target: 0.55
primary_split: scaffold
additional_splits: [random]
calibration_split: scaffold/cal
test_split: scaffold/test
baseline_models: [random_forest, xgboost]
include_chemprop: true
chemprop:
  hpo_trials: 20
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 50
ad:
  k: 5
  fp_radius: 2
  fp_bits: 2048
probability_calibration:
  method: auto
class_balance_handling:
  binary: class_weight              # also evaluate SMOTE
  four_class: class_weight
performance_targets:
  binary_ba: 0.75
  four_class_macro_f1: 0.55
  ece: 0.07
  ad_coverage_test: 0.55
deployment:
  endpoint_id: skin_sensitization
  tier: 1
  fallback_to_tier: 2
```

The deployed backend exposes both the binary and 4-class predictions in the Prediction's provenance. The frontend can choose which to display prominently.

### 5.3 mutagenicity_ames

```yaml
# config.yaml
endpoint: mutagenicity_ames
phase1_dataset: data/curated/mutagenicity_ames/v1.0
heads:
  binary:
    target_column: value_class
    classes: ["non_mutagen", "mutagen"]
    class_kind: binary
    primary_metric: balanced_accuracy
    target: 0.82
primary_split: scaffold
additional_splits: [random]
calibration_split: scaffold/cal
test_split: scaffold/test
baseline_models: [random_forest, xgboost]
include_chemprop: true
chemprop:
  hpo_trials: 20
  ensemble_seeds: [0, 1, 2, 3, 4]
  max_epochs: 50
ad:
  k: 5
  fp_radius: 2
  fp_bits: 2048
probability_calibration:
  method: auto
performance_targets:
  balanced_accuracy: 0.82
  roc_auc: 0.88
  ece: 0.05
  ad_coverage_test: 0.65
deployment:
  endpoint_id: mutagenicity_ames
  tier: 1
  fallback_to_tier: 2
```

### 5.4 eye_irritation (alerts-only)

```yaml
# config.yaml
endpoint: eye_irritation_alerts
mode: structural_alerts
rules_file: python/edeon_models/backends/alerts/rules/eye_irritation.yaml
deployment:
  endpoint_id: eye_irritation
  tier: 1                          # Replaces T2 in the registry
  tier_label: qualitative
  no_training: true
```

The legacy LogP-based eye irritation T2 backend is *deprecated* but not deleted — Phase 0 Task D2 onwards. It remains in code but the alerts backend is registered with the same endpoint_id, taking precedence.

---

## 6. Task Manifest

### Group A — Shared Infrastructure Extensions

#### Task A1: Add MUTAGENICITY_AMES to Endpoint enum
**Depends on:** Phase 0 complete.
**File:** `python/edeon_models/endpoints.py`
**Action:** Add:
```python
MUTAGENICITY_AMES = "mutagenicity_ames"
EYE_IRRITATION_ALERTS = "eye_irritation_alerts"  # Alternative ID for the alerts backend
```

If `eye_irritation` is intended to be served by alerts only, do NOT add a new ID — the alerts backend registers against the existing `EYE_IRRITATION` enum, replacing T2 as the highest-priority backend. Use a clear log message at startup explaining the substitution.

`endpoint_metadata()` for `MUTAGENICITY_AMES`: units="binary", direction="higher = more concern".

**Acceptance:** Enum updated; all downstream code referencing the enum still compiles.

---

#### Task A2: Classification shared module
**Depends on:** A1, Phase 2 infrastructure.
**File:** `python/edeon_train/shared/classification.py`
**Action:**

```python
def train_classification_baseline_with_hpo(
    X_train: np.ndarray,
    y_train: np.ndarray,
    train_scaffolds: list[str],
    model_type: Literal["rf", "xgb"],
    class_kind: Literal["binary", "multi_class"],
    class_weight_mode: Literal["balanced", "smote", "none"] = "balanced",
    n_trials: int = 50,
    cv_folds: int = 5,
    random_state: int = 42,
) -> tuple[BaseEstimator, dict]: ...


def train_chemprop_classifier_ensemble(
    train_smiles, train_y, cal_smiles, cal_y,
    class_kind: Literal["binary", "multi_class"],
    n_classes: int,
    config: dict, output_dir: Path,
    seeds: list[int] = [0, 1, 2, 3, 4],
) -> dict: ...


def predict_classification_ensemble(
    X_or_smiles, checkpoint_dir: Path,
    return_probabilities: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (predicted_class, calibrated_probabilities)."""
```

Implement scaffold-stratified, class-stratified CV (within each scaffold group, stratify by class).

**Acceptance:** Unit test on a synthetic 2-class problem with controlled imbalance achieves BA > 0.85 (the problem is easy when synthetic).

---

#### Task A3: Probability calibration module
**Depends on:** A2.
**File:** `python/edeon_train/shared/probability_calibration.py`
**Action:** Implement per Section 4.2.4. Add multi-class one-vs-rest calibration with renormalisation.

**Acceptance:** On a synthetic miscalibrated binary problem, the auto-selected calibrator reduces ECE by ≥ 50%.

---

#### Task A4: Mutagenicity mini-curation
**Depends on:** A1, Phase 1 infrastructure (`edeon_data` package).
**Files:** `python/edeon_data/endpoints/mutagenicity_ames/{acquire,curate,split,card}.py`
**Action:** Apply the Phase 1 pattern. Sources:

- **Hansen et al. 2009** — Mutagenicity dataset (~6,512 compounds). Reference: Hansen K et al. *J Chem Inf Model* 2009 49:2077. Common public source: the curated CSV maintained on GitHub by the QSAR Toolbox community. **Verify access at runtime**; document URL used.
- **Honma et al. 2019** — modernised Ames dataset (~12,140 compounds). Reference: Honma M et al. *Genes Environ* 2019 41:11. Source: supplementary materials.

Curation specifics:
- Endpoint = `mutagenicity_ames`.
- `value_class`: binary, "mutagen" or "non_mutagen".
- Inclusion: compounds tested in at least one Salmonella strain with consistent result. Positive in any strain → mutagen. Negative in all → non-mutagen. Mixed/inconclusive → drop with `quality_flags=["inconsistent_strains"]`.
- Cross-source dedup: prefer Honma over Hansen for conflicts (more recent, larger panel); flag conflicts.
- Apply shared standardisation (Phase 1 Section 6).
- Generate scaffold + random splits. No time split (no consistent year metadata).

Output: `data/curated/mutagenicity_ames/v1.0/` bundle. Data card per Phase 1 schema.

**Acceptance:** Bundle produced with ~10,000+ unique compounds (after dedup) and ~60/40 class balance. Document final count in PHASE4_NOTES.md.

---

### Group B — Rat acute oral LD50

#### Task B1: Endpoint config and joint regression+classification orchestrator
**Depends on:** A2, A3.
**Files:** `python/edeon_train/endpoints/rat_acute_oral_ld50/{config.yaml, train.py}`
**Action:** Two-head training:
1. Train the regression model using Phase 2 recipe (RF + XGB + Chemprop regression ensemble + split conformal).
2. Train the classification model using Phase 4 recipe (RF + XGB + Chemprop classification ensemble + Platt/isotonic calibration).
3. Save both under the same checkpoint directory:
   ```
   data/checkpoints/rat_acute_oral_ld50/v1.0/
     regression/
       baselines/
       chemprop/
       calibration.npz
       ensemble_weights.yaml
     classification/
       baselines/
       chemprop/
       prob_calibrator.pkl
       ensemble_weights.yaml
     ad_fingerprints.npz   # Shared between heads
     model_card.yaml
     manifest.json
   ```

**Acceptance:** Both heads train. Test set evaluated exactly once (single gate opening covers both heads).

---

#### Task B2: Joint backend implementation
**Depends on:** B1.
**File:** Extend `python/edeon_models/backends/trained/tier1_backend.py` with a `TrainedTier1JointBackend` class (or create a new file `joint_backend.py`) that loads both heads and emits a Prediction with:
- `value.numeric` = regression value (mg/kg, back-transformed from log)
- `ci_lower`/`ci_upper` = conformal CI from regression head
- `provenance.ghs_category` = predicted classification
- `provenance.class_probabilities` = calibrated probability vector per GHS class
- `provenance.regression_components` = baseline + chemprop contributions
- `ad_status` from the shared AD

**Acceptance:** Predicting on 5 known reference compounds returns both regression value with CI and GHS category with probability.

---

#### Task B3: Validation and card
**Depends on:** B2.
**Files:** `card.py` + `docs/TIER1_MODEL_CARDS/rat_acute_oral_ld50.md`
**Action:** Generate per-Phase-2 pattern with additions for the classification head: balanced accuracy, macro F1, ECE, confusion matrix, per-class precision/recall.

**Acceptance:** Card complete in SQLite and as markdown.

---

### Group C — Skin sensitization

#### Task C1: Endpoint config + dual-head trainer
**Depends on:** A2, A3.
**Files:** `python/edeon_train/endpoints/skin_sensitization/{config.yaml, train.py}`
**Action:**

Train both binary and 4-class classifiers, sharing baseline featurization:
1. Binary classifier (sensitizer / non-sensitizer) — most reliable, primary deployed prediction
2. 4-class GHS classifier (non / weak / moderate / strong) — provided as supplementary

```
data/checkpoints/skin_sensitization/v1.0/
  binary/
    baselines/
    chemprop/
    prob_calibrator.pkl
    ensemble_weights.yaml
  four_class/
    baselines/
    chemprop/
    prob_calibrator.pkl     # One-vs-rest calibration
    ensemble_weights.yaml
  ad_fingerprints.npz
  model_card.yaml
  manifest.json
```

Apply class-weight balancing by default; if HPO budget allows, also try SMOTE for binary and pick the better variant.

**Acceptance:** Both heads train; binary BA ≥ 0.72 on cal (target 0.75 on test).

---

#### Task C2: Classification backend implementation
**Depends on:** C1, A2.
**File:** `python/edeon_models/backends/trained/classification_backend.py`

```python
class TrainedClassificationTier1Backend(ModelBackend):
    """Generic T1 backend for classification endpoints with calibrated probabilities."""

    def __init__(self, endpoint: Endpoint, checkpoint_dir: Path, head: str = "binary"): ...

    def predict(self, smiles, conditions=None) -> list[Prediction]:
        # 1. Featurize
        # 2. Predict probabilities per ensemble member
        # 3. Combine via inverse-log-loss weighted mean
        # 4. Apply probability calibrator
        # 5. Compute predicted class as argmax
        # 6. AD scoring
        # 7. Construct Prediction:
        #    - value.categorical = predicted class
        #    - value.binary (for binary) = (predicted_class == positive_class)
        #    - No ci_lower/ci_upper for classification (set to None)
        #    - provenance.class_probabilities = full probability vector
        #    - provenance.calibrator = "platt" or "isotonic"
        #    - provenance.ensemble_components = ...
```

For skin sensitization, the deployed backend exposes the binary head as the primary `value` and the 4-class probabilities in provenance.

**Acceptance:** Predicting on known sensitizers (e.g., DNCB) returns "sensitizer" with high probability.

---

#### Task C3: Card
**Depends on:** C1.
**File:** `card.py` + `docs/TIER1_MODEL_CARDS/skin_sensitization.md`
**Acceptance:** Card complete with calibration plot, ECE, per-class metrics for both heads.

---

### Group D — Mutagenicity Ames

#### Task D1: Curation pipeline
**Depends on:** A4.
**Action:** Execute `edeon-data mutagenicity_ames all`. Curated bundle produced.
**Acceptance:** Bundle at `data/curated/mutagenicity_ames/v1.0/`. Smoke test passes (Phase 1 Task C1).

---

#### Task D2: Endpoint config + classification trainer
**Depends on:** D1, A2, A3.
**Files:** `python/edeon_train/endpoints/mutagenicity_ames/{config.yaml, train.py}`
**Action:** Single-head binary classification. Apply Section 4.2 recipe end-to-end.

**Acceptance:** Trained. Performance: BA ≥ 0.80 on cal, AUC ≥ 0.86.

---

#### Task D3: Backend deployment
**Depends on:** D2, C2.
**Action:** Reuse `TrainedClassificationTier1Backend` (head="binary"). Register in `build_default_registry()`.

**Acceptance:** `reg.get(Endpoint.MUTAGENICITY_AMES).tier() == 1`. Predicts on benzo[a]pyrene SMILES returns "mutagen" with P > 0.85.

---

#### Task D4: Card
**Depends on:** D2.
**File:** `card.py` + `docs/TIER1_MODEL_CARDS/mutagenicity_ames.md`
**Acceptance:** Card complete.

---

### Group E — Eye Irritation Alerts

#### Task E1: Alerts rules file
**Depends on:** Phase 0 enums.
**File:** `python/edeon_models/backends/alerts/rules/eye_irritation.yaml`
**Action:** Populate with at least 10 alerts per Section 4.3 example, refining SMARTS for correctness (the example patterns are illustrative). Each rule has: id, smarts, category (severe/moderate/mild), description, references.

Verify SMARTS by spot-checking against known reference compounds:
- Formaldehyde (`C=O`) → aldehyde alert
- Glycidol (epoxide-containing) → epoxide alert
- Phenyl isocyanate → isocyanate alert
- Acetone (`CC(=O)C`) → should NOT match any alert (acceptable to be flagged only by ketone-Michael acceptor SMARTS, but watch over-flagging)

**Acceptance:** Rules file validates against a schema (pydantic model in `alerts/__init__.py`).

---

#### Task E2: Alerts backend
**Depends on:** E1, Phase 0 ModelBackend interface.
**File:** `python/edeon_models/backends/alerts/alerts_backend.py`

```python
class StructuralAlertsBackend(ModelBackend):
    """Tier-1-alternative backend for endpoints where quantitative prediction is
    not feasible. Emits qualitative alerts based on SMARTS pattern matching."""

    def __init__(self, endpoint: Endpoint, rules_file: Path): ...

    def endpoint(self) -> Endpoint: return self._endpoint
    def tier(self) -> int: return 1
    def version(self) -> str: return self._rules["version"]

    def predict(self, smiles, conditions=None) -> list[Prediction]:
        results = []
        for s in smiles:
            mol = Chem.MolFromSmiles(s)
            if mol is None:
                results.append(self._unparseable(s))
                continue
            matched = []
            for rule in self._rules["rules"]:
                pattern = Chem.MolFromSmarts(rule["smarts"])
                if pattern and mol.HasSubstructMatch(pattern):
                    matched.append({
                        "id": rule["id"],
                        "category": rule["category"],
                        "description": rule["description"],
                        "references": rule["references"],
                    })
            results.append(self._build_prediction(s, matched))
        return results

    def applicability_domain(self, smiles):
        return [ADStatus.UNKNOWN] * len(smiles)  # Alerts have no AD

    def metadata(self) -> ModelCard:
        return ModelCard(
            ...,
            tier=1,
            description=(
                "Qualitative structural alerts for eye irritation potential. "
                "This is NOT a quantitative prediction. Absence of alerts does NOT "
                "imply non-irritancy."
            ),
            intended_use="Early-stage screening for known eye-irritating chemotypes.",
            not_intended_for=[
                "Regulatory dossier submission",
                "Quantitative risk assessment",
                "Replacement of OECD 405 / 437 testing",
            ],
            known_failure_modes=[
                "Compounds not matching any alert may still be irritants",
                "SMARTS patterns are necessarily approximate",
                "Mechanism-specific irritation (e.g., surfactant action) requires additional consideration",
            ],
            ...
        )
```

The Prediction for the alerts backend:
- `value.categorical = "no_alerts" | "alerts_present"`
- `provenance.matched_alerts = [{id, category, description, references}, ...]`
- `provenance.alert_count_by_category = {"severe": 0, "moderate": 1, ...}`
- `ad_status = ADStatus.UNKNOWN`
- `warnings = ["Qualitative screening only — not a quantitative prediction"]`

**Acceptance:** Predicting on formaldehyde returns "alerts_present" with at least one matched alert. Predicting on ethanol returns "no_alerts".

---

#### Task E3: Register alerts backend
**Depends on:** E2.
**Action:** Extend `build_default_registry()` to register the alerts backend with `Endpoint.EYE_IRRITATION` and tier=1. The legacy T2 LogP-based eye irritation backend remains in code but is now superseded.

Log a clear startup message: `"Eye irritation: T1 backend is qualitative structural alerts (no quantitative model)."`

**Acceptance:** `reg.get(Endpoint.EYE_IRRITATION)` returns the alerts backend.

---

#### Task E4: Rationale document
**Depends on:** E1.
**File:** `docs/EYE_IRRITATION_ALERTS_RATIONALE.md`
**Action:** Short document explaining why eye irritation is alerts-only:
- Public data is fragmented (BCOP, Draize, EpiOcular, etc.) with low cross-test concordance
- Quantitative QSAR models in published literature achieve modest R² and don't generalize across assays
- The honest move is qualitative alerts with citations rather than fake numeric precision
- Future option: T3 integration with EPA T.E.S.T (BSD-licensed, locally executable)

**Acceptance:** Document committed.

---

### Group F — Frontend Updates

#### Task F1: Toxicity panel layout refresh
**Depends on:** B2, C2, D3, E3.
**Files:** Locate the existing toxicity panel component in `src/components/`. Replace contents:

For Rat LD50:
- Display numeric value with units (mg/kg) and CI from PredictionDisplay component (Phase 0)
- Show GHS category as a colour-coded badge (Cat 1 red, Cat 5 green, etc.)
- Tooltip on badge shows class probability distribution

For Skin sensitization:
- Show binary predicted class as the primary badge ("Sensitizer" / "Non-sensitizer")
- Show calibrated probability as a horizontal bar
- Below: small 4-class breakdown with probability per class (collapsible)

For Mutagenicity (NEW):
- Show "Mutagen" / "Non-mutagen" badge
- Show calibrated probability
- AD status badge (in/borderline/out)

For Eye irritation:
- Replace previous numeric display with an alerts list
- If no alerts: green "No structural alerts identified" with caveat tooltip ("Absence of alerts does not guarantee non-irritancy")
- If alerts present: red/orange list of matched alerts with descriptions and citation links

**Acceptance:** Toxicity panel renders all four endpoints in the new style.

---

#### Task F2: Mammalian risk visual aggregator (optional, recommended)
**Depends on:** F1.
**Action:** A summary "mammalian risk indicator" at the top of the panel — colour-coded summary based on:
- Rat LD50 GHS category (most weight)
- Sensitizer status (moderate weight)
- Mutagen status (high weight if positive)
- Number of eye irritation alerts (low weight, structural alerts are conservative)

This is a *visual* aggregator, not a trained composite — the rules are transparent and documented in `docs/PHASE4_NOTES.md`. Think of it as analogous to the GUS gauge: it summarises across components.

**Acceptance:** Risk indicator renders. Hovering shows the contributing factors.

---

### Group G — Validation and CI

#### Task G1: Mammalian regression CI
**Depends on:** All previous tasks.
**File:** `.github/workflows/tier1_mammalian_regression.yml`

Same pattern as Phase 2/3 regression CI: load T1 backends, predict on a fixed 20-compound reference set, compare to stored expected values within tolerance.

Reference compounds should include:
- Caffeine (low rat tox, non-sensitizer, non-mutagen)
- DNCB (strong sensitizer)
- Benzo[a]pyrene (potent mutagen)
- Formaldehyde (severe eye alerts, mutagen)
- Glyphosate (low rat tox)
- ... etc.

**Acceptance:** CI green on first commit.

---

#### Task G2: End-to-end mammalian test
**Depends on:** F1.
**File:** `tests/integration/test_t1_mammalian_e2e.py`
**Action:** Test that the toxicity panel response from the Tauri command contains all four endpoints with appropriate tier=1 status.

**Acceptance:** Test passes.

---

#### Task G3: Benchmark results document
**Depends on:** B3, C3, D4.
**File:** `docs/PHASE4_BENCHMARK_RESULTS.md`
**Action:** Auto-generated table with metrics per endpoint (BA, F1, ECE for classification; RMSE, R², coverage for regression).

**Acceptance:** Document generated.

---

#### Task G4: Classification protocol document
**Depends on:** A2, A3, B1, C1, D2.
**File:** `docs/PHASE4_CLASSIFICATION_PROTOCOL.md`
**Action:** Document the full classification methodology (Section 4.2): class imbalance handling, ensemble combination via inverse log-loss weights, Platt vs isotonic calibration choice, ECE evaluation. This is the methods reference for Paper 3 (or a follow-on paper).

**Acceptance:** Document committed.

---

## 7. Acceptance Criteria for Phase 4 Complete

Phase 4 is complete when ALL of the following hold:

1. `Endpoint.MUTAGENICITY_AMES` is in the enum and referenced consistently.
2. Mutagenicity Phase 1 mini-bundle exists at `data/curated/mutagenicity_ames/v1.0/`.
3. Rat LD50 T1 backend (regression + classification heads) trained, deployed, registered. Targets met or documented gap.
4. Skin sensitization T1 backend (binary + 4-class) trained, deployed, registered. Targets met or gap documented.
5. Mutagenicity Ames T1 backend trained, deployed, registered.
6. Eye irritation alerts T1 backend registered; legacy T2 backend superseded.
7. Probability calibration applied (ECE < target) for all classification endpoints.
8. Toxicity panel UI updated with new component layouts; eye irritation displays alerts list.
9. Mammalian regression CI workflow passes.
10. `PHASE4_CLASSIFICATION_PROTOCOL.md`, `EYE_IRRITATION_ALERTS_RATIONALE.md`, `PHASE4_BENCHMARK_RESULTS.md`, `PHASE4_NOTES.md` are populated.
11. All four endpoints' model cards persisted to SQLite and as markdown.

---

## 8. Out of Scope (for Phase 4)

Do **not** in Phase 4:

- Train models for ecotox endpoints (Phase 2) or fate endpoints (Phase 3).
- Train models for BCF or photostability (later phases).
- Implement EPA T.E.S.T as a T3 integration (documented as future option).
- Build the cross-species selectivity module (Paper 2 / Phase 5).
- Replace the bioisostere engine or 3D viewer docking (Phase 6).
- Add new endpoints beyond those specified.
- Implement multitask learning across mammalian endpoints (potential future improvement; out of scope here).
- Modify Phase 1 curation rules.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Mutagenicity Hansen-Honma source access changes / URL moves | Document URLs used; if access fails, accept Hansen alone (~6500 compounds) and document smaller dataset in card |
| Skin sensitization 4-class is too imbalanced for reliable model | Document; fall back to binary as the only deployed head; 4-class becomes "experimental, not deployed" |
| Probability calibration over-corrects with small cal sets | Use isotonic regression only when n_cal ≥ 500; otherwise Platt |
| ECE remains > target | Document; calibration is hard with small data; may indicate inherent limits — be honest in card |
| Eye irritation alerts trigger too aggressively (over-flagging) | Test on a small panel of confirmed non-irritants; if false-positive rate > 30%, refine SMARTS or move some "severe" → "moderate" |
| Eye irritation alerts miss known irritants | Expected — that's why "absence of alerts" carries a disclaimer; document |
| Test set accidentally evaluated multiple times | Hard gate (Phase 2 Task A2) catches |
| Class imbalance handling regresses overall BA | Compare class_weight vs SMOTE on cal; pick whichever is higher; document choice |

---

## 10. Conventions

- Random seeds: 42 for splits and calibration choice; [0, 1, 2, 3, 4] for ensembles.
- Provenance fields for classification predictions: `class_probabilities`, `calibrator_method`, `ensemble_components`, `predicted_class_probability`.
- Provenance fields for alerts predictions: `matched_alerts`, `alert_count_by_category`, `total_alerts`.
- Naming: `snake_case` Python, classification heads in subdirectories under endpoint checkpoint dirs.

---

## 11. Handoff Notes

Phase 4 outputs feed:

- **Paper 3** — the regression endpoints (rat LD50 numeric head) and classification protocol contribute to the benchmark paper.
- **Phase 5 / 6** — the structural alerts pattern from Section 4.3 is generalisable; later phases may build PAINS, BRENK, Cramer-class alerts as additional structural-alert backends sharing the same `StructuralAlertsBackend` class.
- **Commercial pitch** — the toxicity panel is now the second most-improved module after the honeycomb. The honest treatment of eye irritation (alerts instead of fake LD50) is itself a credibility signal to expert evaluators.
- **Regulatory positioning** — mutagenicity with calibrated probabilities and AD-aware predictions becomes one of the most defensible endpoints in the product. Regulatory affairs will care about the ECE numbers and the model card's traceability.

The combination of Phase 2 (ecotox) + Phase 3 (fate) + Phase 4 (mammalian) covers the EU/EPA "core regulatory endpoint set" with trained T1 models. After Phase 4, the only major endpoints remaining as T2 LogP-based are BCF (small dataset; Phase 5), photostability (data fundamentally limited; qualitative replacement), and selectivity (Paper 2 territory). The product's "we ship LogP heuristics" criticism evaporates for the majority of cells.

---

## 12. Deviation Log

Maintain `docs/PHASE4_NOTES.md` with:
- Hansen/Honma source URLs used and access dates.
- Final dataset sizes after curation.
- HPO best hyperparameters per endpoint.
- ECE before and after calibration per endpoint.
- Cases where SMOTE outperformed class_weight (or vice versa).
- Eye irritation SMARTS refinements made from the example rules.
- Test set evaluation timestamps (proving the gate fired exactly once per endpoint).
- Mammalian risk aggregator weights (the Task F2 rules).

---

**End of Phase 4 Specification.**
