# Edeon ModelCard Schema Specification

This document provides complete, field-by-field specifications of the `ModelCard` schema used throughout Edeon's Phase 0 unified predictor architecture. The ModelCard encapsulates critical metadata, training lineage, cross-validation metrics, applicability domain limits, and uncertainty quantification rules for every predictive backend in the platform.

---

## 1. Schema Architecture Overview

The `ModelCard` model is built on Pydantic v2 and enables strong type enforcement, validation, and JSON/YAML round-trip serialization.

```
                  ┌─────────────────────────────────┐
                  │            ModelCard            │
                  └────────────────┬────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐     ┌──────────────────┐      ┌──────────────────┐
│ TrainingDataInfo │     │PerformanceMetrics│      │   ADDefinition   │
└──────────────────┘     └──────────────────┘      └──────────────────┘
```

---

## 2. Root-Level ModelCard Fields

The following table documents every root-level field in the `ModelCard` schema:

| Field Name | Type | Required / Optional | Description |
| :--- | :--- | :--- | :--- |
| `model_id` | `str` | **Required** | Unique string identifier of the backend (e.g. `{endpoint}.t{tier}.{version}`). |
| `name` | `str` | **Required** | Clean, human-readable name of the model. |
| `version` | `str` | **Required** | Semantic version string of the model code and weights (e.g., `"1.0.0"`). |
| `tier` | `int` | **Required** | Integer mapping to `Tier` (1 = Reference, 2 = Baseline, 3 = External, 4 = User). |
| `endpoint` | `str` | **Required** | The canonical endpoint enum value served by the backend (e.g. `"bee_acute_oral_ld50"`). |
| `description` | `str` | **Required** | Short technical summary of the model design, architecture, and training rationale. |
| `intended_use` | `str` | **Required** | Explicit description of the scenarios the model is designed to support. |
| `not_intended_for` | `list[str]` | Optional (Default: `[]`) | Limitations or circumstances where utilizing the model is discouraged. |
| `training_data` | `TrainingDataInfo` | Optional (Default: `None`) | Structured object containing details on the training dataset size and sources. |
| `performance` | `PerformanceMetrics` | Optional (Default: `None`) | Structured object holding hold-out validation metrics and cross-validation counts. |
| `applicability_domain` | `ADDefinition` | Optional (Default: `None`) | Structured description of the applicability domain limits and thresholds. |
| `uncertainty_method` | `str` | Optional (Default: `None`) | Name of the uncertainty strategy utilized if UQ bounds are enabled (e.g. `"ConformalUQ"`). |
| `known_failure_modes` | `list[str]` | Optional (Default: `[]`) | Explicit list of chemical categories or functional groups prone to higher errors. |
| `references` | `list[str]` | Optional (Default: `[]`) | Bibliographical references and papers supporting the model. |
| `license` | `str` | Optional (Default: `"Proprietary"`) | Licensing terms governing model usage. |
| `created` | `datetime` | Optional (Default: `utcnow`) | ISO 8601 creation date and time. |
| `authors` | `list[str]` | Optional (Default: `[]`) | List of scientific authors and developers responsible for the model. |

---

## 3. Nested Metadata Specifications

### 3.1. TrainingDataInfo
Holds details of the dataset used to train the model backend.

| Field Name | Type | Required / Optional | Description |
| :--- | :--- | :--- | :--- |
| `n_compounds` | `int` | **Required** | Number of unique organic/inorganic structures in the training set. |
| `sources` | `list[str]` | **Required** | Standard database or literature names (e.g. `["EPA ECOTOX", "ChEMBL"]`). |
| `sha256` | `str` | Optional | SHA-256 cryptographic hash of the standardized training SMILES file. |
| `split_strategy` | `str` | Optional | Partition strategy used during validation (e.g. `"scaffold"`, `"random"`, `"time"`). |
| `license` | `str` | Optional | Data license details (e.g., `"CC-BY-4.0"`). |

### 3.2. PerformanceMetrics
Describes validation statistics calculated on a held-out test set or via cross-validation.

| Field Name | Type | Required / Optional | Description |
| :--- | :--- | :--- | :--- |
| `metrics` | `dict[str, float]` | **Required** | Dictionary mapping metric names to their numeric scores (e.g. `{"rmse": 0.35, "r2": 0.81}`). |
| `test_set_n` | `int` | Optional | Size of the validation subset used to calculate test metrics. |
| `cv_folds` | `int` | Optional | Number of cross-validation folds executed during model validation. |
| `calibration_coverage_95` | `float` | Optional | Actual empirical coverage of predictions within 95% confidence intervals. |

### 3.3. ADDefinition
Describes applicability domain boundary criteria to screen out invalid or out-of-domain query structures.

| Field Name | Type | Required / Optional | Description |
| :--- | :--- | :--- | :--- |
| `method` | `str` | **Required** | Strategy name (e.g. `"tanimoto_knn"`, `"leverage"`, `"ensemble_variance"`, `"none"`). |
| `threshold` | `float` | Optional | Numeric boundary threshold. Queries exceeding this are flagged OUT/BORDERLINE. |
| `k` | `int` | Optional | Neighbor count parameter for distance-based applicability domains. |
| `training_set_size` | `int` | Optional | Number of training compounds mapped inside the AD search index. |
| `notes` | `str` | Optional | Qualitative explanations of boundary rules. |

---

## 4. Comprehensive Examples

### 4.1. Tier 1 (Reference) Backend Model Card
A highly detailed QSAR Random Forest regression model serving the Honeybee Acute Oral toxicity endpoint, utilizing a nearest-neighbor Tanimoto applicability domain and Conformal UQ bounds.

```yaml
model_id: bee_acute_oral_ld50.t1.1.2.0
name: Honeybee Acute Oral QSAR Reference
version: 1.2.0
tier: 1
endpoint: bee_acute_oral_ld50
description: >
  Standardized Random Forest regression model utilizing Morgan circular fingerprints
  (radius=2, 2048-bits) trained on curated EPA ECOTOX datasets.
intended_use: >
  High-throughput screening of novel pesticide active ingredients to estimate
  acute oral toxicity in Apis mellifera.
not_intended_for:
  - Sub-lethal behavioral effect predictions
  - Formulation synergy assays (multiple active ingredients)
training_data:
  n_compounds: 452
  sources:
    - EPA ECOTOX Database (2025 Release)
    - EFSA Draft Assessment Reports
  sha256: 4fa2c681283d5aee20412b192eab85601249b6ce8b7b25ad7521a08ea15a99cc
  split_strategy: scaffold
  license: Public Domain
performance:
  metrics:
    r2: 0.812
    rmse: 0.385
    mae: 0.291
  test_set_n: 90
  cv_folds: 5
  calibration_coverage_95: 0.942
applicability_domain:
  method: tanimoto_knn
  threshold: 0.352
  k: 5
  training_set_size: 452
  notes: Flagged OUT if mean Tanimoto distance to 5 nearest training compounds > 0.352.
uncertainty_method: ConformalUQ
known_failure_modes:
  - Organophosphates with unusual heavy metal complexes (out of AD)
  - Synthetic short peptides
references:
  - Smith et al., Journal of Agrochemical Science, 2026, 44(2), 112-124
  - Edeon Scientific Whitepaper — Phase 0 Unified Predictors
license: Proprietary
created: '2026-05-29T08:00:00Z'
authors:
  - Dr. Clara Hughes (Lead Scientist)
  - Dr. Sarah Patel (QSAR Engineer)
```

### 4.2. Tier 2 (Baseline) Backend Model Card
A basic logP-based baseline estimator serving as a fallback for the same Honeybee Oral toxicity endpoint, requiring no UQ or applicability domain.

```yaml
model_id: bee_acute_oral_ld50.t2.1.0.0
name: Honeybee Acute Oral logP Baseline
version: 1.0.0
tier: 2
endpoint: bee_acute_oral_ld50
description: >
  Simple baseline predictor mapping octanol-water partition coefficients (logP)
  to LD50 ranges based on historical regression rules of organic compounds.
intended_use: >
  Instant fallback estimates when Tier 1 models are out of domain or unavailable,
  and for initial rough screening of standard organic compounds.
not_intended_for:
  - Inorganic salts
  - Organometallics
  - High-precision regulatory submission dossiers
training_data:
  n_compounds: 120
  sources:
    - Historical pesticide baseline manuals
  split_strategy: none
performance:
  metrics:
    r2: 0.44
    rmse: 0.95
applicability_domain:
  method: none
uncertainty_method: null
known_failure_modes:
  - Ionic compounds (poor partition coefficient estimation)
references:
  - Agrochemical Toxicological Manual, Vol 2
license: Proprietary
created: '2026-05-28T12:00:00Z'
authors:
  - Agrochemical Baseline Consortium
```
